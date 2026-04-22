"""
product_expert.py  v2.2
Live mode: scrapes product page (Amazon / TikTok Shop / generic URL) with httpx,
extracts real title / description / price hints, then feeds them to LLM.
No paid API required.
"""
import asyncio
import re
import uuid
import html as html_lib
from typing import Optional
from pydantic import BaseModel

import httpx
import pandas as pd

from config.settings import settings
from utils.mock_factory import MockFactory
from services.llm_service import llm_service


# ── Pydantic models ───────────────────────────────────────────────────────────

class ProductSchema(BaseModel):
    product_id: str
    origin_url: str
    product_name: str
    supplier: str
    supplier_price_usd: float
    weight_kg: float
    selling_price_usd: float
    amazon_rating: float
    amazon_review_count: int
    amazon_monthly_sales: int
    google_trend_score: int
    trend_direction: str


class ProfitModel(BaseModel):
    selling_price: float
    purchase_cost: float
    first_leg_cost: float
    last_leg_cost: float
    platform_fee: float
    return_reserve: float
    net_profit: float
    roi_pct: float
    breakeven_price: float


class ProductAnalysisResult(BaseModel):
    product: ProductSchema
    profit_model: ProfitModel
    selection_score: int
    analysis_report: str


# ── URL product scraper ───────────────────────────────────────────────────────

class ProductScraper:
    """
    Lightweight product page scraper.
    Extracts: title, description, price, rating, review count from
    Amazon / TikTok Shop / generic e-commerce pages.
    Uses httpx with browser-like headers; verify=False for Windows SSL.
    """

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    async def scrape(self, url: str) -> Optional[dict]:
        """Fetch page HTML and extract structured product info."""
        print(f"[ProductScraper] Fetching: {url}")
        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=5.0),
                follow_redirects=True,
                headers=self._HEADERS,
            ) as client:
                resp = await client.get(url)
                html = resp.text
        except Exception as e:
            print(f"[ProductScraper] Fetch error: {type(e).__name__}: {e}")
            return None

        info = self._extract(html, url)
        if info:
            print(f"[ProductScraper] Extracted: {info.get('product_name', '(no title)')[:60]}")
        return info

    def _extract(self, html: str, url: str) -> dict:
        """Extract product fields from raw HTML using regex patterns."""

        def _first(patterns: list[str], text: str, default: str = "") -> str:
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE | re.DOTALL)
                if m:
                    raw = m.group(1).strip()
                    return html_lib.unescape(raw)[:300]
            return default

        def _float(patterns: list[str], text: str, default: float = 0.0) -> float:
            raw = _first(patterns, text)
            nums = re.findall(r"[\d,]+\.?\d*", raw.replace(",", ""))
            return float(nums[0]) if nums else default

        # ── title ────────────────────────────────────────────────────────────
        title = _first([
            r'<span[^>]+id=["\']productTitle["\'][^>]*>(.*?)</span>',   # Amazon
            r'<h1[^>]+class=["\'][^"\']*product[^"\']*["\'][^>]*>(.*?)</h1>',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<title>(.*?)</title>',
        ], html, default="Unknown Product")

        # ── description ──────────────────────────────────────────────────────
        desc = _first([
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<div[^>]+id=["\']productDescription["\'][^>]*>(.*?)</div>',
        ], html)

        # ── price ─────────────────────────────────────────────────────────────
        price_raw = _first([
            r'<span[^>]+class=["\'][^"\']*a-price-whole["\'][^>]*>([\d,]+)',   # Amazon
            r'"price"\s*:\s*"?\$?([\d,]+\.?\d*)',
            r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)["\']',
        ], html)
        scraped_price = float(re.sub(r"[^0-9.]", "", price_raw)) if price_raw else 0.0

        # ── rating ────────────────────────────────────────────────────────────
        rating = _float([
            r'<span[^>]+class=["\'][^"\']*a-icon-alt["\'][^>]*>([\d.]+)\s*out',
            r'"ratingValue"\s*:\s*"?([\d.]+)',
            r'"aggregateRating".*?"ratingValue"\s*:\s*"?([\d.]+)',
        ], html)
        if rating > 5:
            rating = 0.0

        # ── review count ──────────────────────────────────────────────────────
        review_count = int(_float([
            r'<span[^>]+id=["\']acrCustomerReviewText["\'][^>]*>([\d,]+)',
            r'"reviewCount"\s*:\s*"?([\d,]+)',
            r'"ratingCount"\s*:\s*"?([\d,]+)',
        ], html))

        # ── detect platform ───────────────────────────────────────────────────
        is_amazon   = "amazon." in url.lower()
        is_tiktok   = "tiktok." in url.lower()

        return {
            "product_name":    title,
            "description":     desc,
            "scraped_price":   scraped_price,
            "amazon_rating":   rating,
            "amazon_review_count": review_count,
            "is_amazon":       is_amazon,
            "is_tiktok_shop":  is_tiktok,
            "data_source":     "scraped",
        }


# ── Profit calculator ─────────────────────────────────────────────────────────

class ProfitCalculator:
    def __init__(self):
        self.first_leg_rate   = settings.FIRST_LEG_FEE_PER_KG
        self.last_leg_fee     = settings.LAST_LEG_FEE_PER_UNIT
        self.platform_fee_rate = settings.PLATFORM_FEE_RATE
        self.return_rate      = settings.RETURN_RATE

    def calculate(
        self,
        selling_price: float,
        purchase_cost: float,
        weight_kg: float,
        first_leg_rate: Optional[float] = None,
        last_leg_fee: Optional[float] = None,
        platform_fee_rate: Optional[float] = None,
    ) -> ProfitModel:
        flr = first_leg_rate   or self.first_leg_rate
        llf = last_leg_fee     or self.last_leg_fee
        pfr = platform_fee_rate or self.platform_fee_rate

        first_leg_cost = weight_kg * flr
        last_leg_cost  = llf
        platform_fee   = selling_price * pfr
        gross_profit   = selling_price - purchase_cost - first_leg_cost - last_leg_cost - platform_fee
        return_reserve = max(0, gross_profit * self.return_rate)
        net_profit     = gross_profit - return_reserve
        roi_pct        = (net_profit / purchase_cost * 100) if purchase_cost > 0 else 0.0
        denom          = 1 - pfr * (1 + self.return_rate)
        breakeven      = (purchase_cost + first_leg_cost + last_leg_cost) / denom if denom > 0 else 0.0

        return ProfitModel(
            selling_price  = round(selling_price, 2),
            purchase_cost  = round(purchase_cost, 2),
            first_leg_cost = round(first_leg_cost, 2),
            last_leg_cost  = round(last_leg_cost, 2),
            platform_fee   = round(platform_fee, 2),
            return_reserve = round(return_reserve, 2),
            net_profit     = round(net_profit, 2),
            roi_pct        = round(roi_pct, 1),
            breakeven_price= round(breakeven, 2),
        )

    def batch_simulate(
        self,
        purchase_cost: float,
        weight_kg: float,
        price_range: tuple = (9.99, 49.99),
        steps: int = 10,
    ) -> pd.DataFrame:
        prices  = [price_range[0] + (price_range[1] - price_range[0]) * i / (steps - 1) for i in range(steps)]
        records = []
        for price in prices:
            pm = self.calculate(price, purchase_cost, weight_kg)
            records.append({
                "selling_price": pm.selling_price,
                "net_profit":    pm.net_profit,
                "roi_pct":       pm.roi_pct,
            })
        return pd.DataFrame(records)


# ── Product Expert ────────────────────────────────────────────────────────────

class ProductExpert:

    def __init__(self):
        self.profit_calc = ProfitCalculator()
        self._scraper    = ProductScraper()

    async def fetch_product_data(
        self,
        origin_url: str,
        selling_price: float,
        image_path: Optional[str] = None,
    ) -> dict:

        if settings.DEBUG_MODE:
            return MockFactory.product_metadata(origin_url, selling_price)

        # ── Live mode: scrape the real product page ───────────────────────
        scraped = await self._scraper.scrape(origin_url)

        if scraped and scraped.get("product_name", "Unknown Product") != "Unknown Product":
            # Build a real meta dict from scraped data
            # Use scraped price if user didn't provide one, else keep user's price
            effective_price = selling_price if selling_price > 0 else scraped.get("scraped_price", 29.99)

            # Estimate supplier price as ~20% of selling price (conservative default)
            estimated_supplier = round(effective_price * 0.20, 2)

            return {
                "product_id":           str(uuid.uuid4())[:8],
                "origin_url":           origin_url,
                "product_name":         scraped["product_name"],
                "description":          scraped.get("description", ""),
                "supplier":             "待查询（请在1688搜索对应商品）",
                "supplier_price_usd":   estimated_supplier,
                "weight_kg":            0.5,          # default; user can override via params
                "selling_price_usd":    effective_price,
                "amazon_rating":        scraped.get("amazon_rating", 0.0),
                "amazon_review_count":  scraped.get("amazon_review_count", 0),
                "amazon_monthly_sales": 0,            # not available without paid API
                "google_trend_score":   50,           # neutral default
                "trend_direction":      "稳定",
                "earliest_viral_date":  "未知",
                "viral_platform":       "未知",
                "recent_amazon_reviews": [],
                "data_source":          "scraped",
            }

        # ── Graceful fallback: mock with warning ─────────────────────────
        print("[ProductExpert] Scraping failed, falling back to mock data")
        meta = MockFactory.product_metadata(origin_url, selling_price)
        meta["data_source"]    = "mock_fallback"
        meta["origin_url"]     = origin_url
        meta["product_name"]   = f"[无法抓取] {origin_url[:60]}"
        return meta

    def _calculate_selection_score(self, meta: dict, profit: ProfitModel) -> int:
        score = 0.0
        score += min(3.0, profit.roi_pct / 100 * 3.0)

        trend = meta.get("google_trend_score", 0)
        direction = meta.get("trend_direction", "稳定")
        ts = trend / 100 * 2.5
        if direction == "上升":
            ts *= 1.2
        elif direction == "下降":
            ts *= 0.6
        score += min(2.5, ts)

        monthly = meta.get("amazon_monthly_sales", 0)
        rating  = meta.get("amazon_rating", 0)
        ms = (1.5 if monthly > 1000 else 0.8 if monthly > 200 else 0) + \
             (1.0 if rating >= 4.0 else 0.5 if rating >= 3.5 else 0)
        score += ms

        reviews = meta.get("amazon_review_count", 0)
        score += (2.0 if reviews < 100 else 1.5 if reviews < 500 else
                  1.0 if reviews < 2000 else 0.3)

        return min(10, round(score))

    async def analyze(
        self,
        origin_url: str,
        selling_price: float,
        image_path: Optional[str] = None,
        first_leg_rate: Optional[float] = None,
        last_leg_fee: Optional[float] = None,
    ) -> ProductAnalysisResult:

        meta   = await self.fetch_product_data(origin_url, selling_price, image_path)
        profit = self.profit_calc.calculate(
            selling_price = meta["selling_price_usd"],
            purchase_cost = meta["supplier_price_usd"],
            weight_kg     = meta["weight_kg"],
            first_leg_rate= first_leg_rate,
            last_leg_fee  = last_leg_fee,
        )
        product = ProductSchema(
            product_id         = meta["product_id"],
            origin_url         = meta["origin_url"],
            product_name       = meta["product_name"],
            supplier           = meta["supplier"],
            supplier_price_usd = meta["supplier_price_usd"],
            weight_kg          = meta["weight_kg"],
            selling_price_usd  = meta["selling_price_usd"],
            amazon_rating      = meta["amazon_rating"],
            amazon_review_count= meta["amazon_review_count"],
            amazon_monthly_sales=meta["amazon_monthly_sales"],
            google_trend_score = meta["google_trend_score"],
            trend_direction    = meta["trend_direction"],
        )
        score  = self._calculate_selection_score(meta, profit)
        report = await llm_service.analyze_product(meta, profit.net_profit)

        return ProductAnalysisResult(
            product        = product,
            profit_model   = profit,
            selection_score= score,
            analysis_report= report,
        )


# singletons
product_expert    = ProductExpert()
profit_calculator = ProfitCalculator()
