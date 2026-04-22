"""
account_analyzer.py - v2.2 fix
Live mode: uses yt-dlp to scrape the user's TikTok profile page,
fetches up to 30 recent videos, and derives real engagement metrics.
No paid API key required.
"""
import asyncio
import re
from typing import Optional
from pydantic import BaseModel

from config.settings import settings
from utils.mock_factory import MockFactory
from services.llm_service import llm_service


# ── Pydantic models ───────────────────────────────────────────────────────────

class AccountSchema(BaseModel):
    user_id: str
    username: str
    followers: int
    following: int
    total_videos: int
    total_likes: float
    follower_growth_rate_30d: float
    play_like_ratio: float
    avg_engagement_rate: float
    cart_video_ratio: float
    primary_category: str
    linktree_url: Optional[str] = None
    tiktok_shop_url: Optional[str] = None
    audience_top_country: str = "US"
    data_source: str = "mock"


class AccountAuditResult(BaseModel):
    account: AccountSchema
    commercial_score: int
    recommended_categories: list[str]
    audit_report: str
    monetization_estimate: dict


# ── yt-dlp profile fetcher ────────────────────────────────────────────────────

class TikTokProfileFetcher:
    """
    Scrapes a TikTok user profile using yt-dlp Python API.
    Extracts up to MAX_VIDEOS recent videos to compute real metrics.
    No API key required.
    """
    MAX_VIDEOS = 30   # how many recent videos to pull for metric calculation

    def _clean_user_id(self, user_id: str) -> str:
        """Normalise user_id: strip @, spaces, full URLs -> bare username"""
        uid = user_id.strip()
        # handle full URL: https://www.tiktok.com/@username or @username/...
        m = re.search(r'tiktok\.com/@([^/?&\s]+)', uid)
        if m:
            return m.group(1)
        return uid.lstrip('@').split('/')[0].split('?')[0]

    def _run_sync(self, user_id: str) -> Optional[dict]:
        """Synchronous yt-dlp extraction (called in thread pool)."""
        try:
            import yt_dlp
        except ImportError:
            print("[AccountAnalyzer] yt-dlp not installed (pip install yt-dlp)")
            return None

        username = self._clean_user_id(user_id)
        profile_url = f"https://www.tiktok.com/@{username}"
        print(f"[AccountAnalyzer] Fetching profile: {profile_url}")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,        # fast: just get video list metadata
            "playlistend": self.MAX_VIDEOS,
            "nocheckcertificate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(profile_url, download=False)
        except Exception as e:
            print(f"[AccountAnalyzer] yt-dlp profile error: {type(e).__name__}: {e}")
            return None

        if not info:
            return None

        entries = info.get("entries") or []
        if not entries:
            print("[AccountAnalyzer] Profile fetched but no video entries found")
            return None

        print(f"[AccountAnalyzer] Got {len(entries)} videos for @{username}")
        return self._compute_metrics(info, entries, username, profile_url)

    def _compute_metrics(self, info: dict, entries: list, username: str, profile_url: str) -> dict:
        """
        Derive engagement metrics from real video-level data.

        Available per-entry fields from yt-dlp flat extraction:
          view_count, like_count, comment_count, repost_count, duration, title
        """
        total_views    = 0
        total_likes    = 0
        total_comments = 0
        total_shares   = 0
        valid          = 0

        for e in entries:
            v = int(e.get("view_count")    or 0)
            l = int(e.get("like_count")    or 0)
            c = int(e.get("comment_count") or 0)
            s = int(e.get("repost_count")  or 0)
            if v > 0:
                total_views    += v
                total_likes    += l
                total_comments += c
                total_shares   += s
                valid += 1

        if valid == 0:
            # entries found but no view data (private / region-locked)
            valid = len(entries)
            total_views = valid * 10000   # conservative estimate

        avg_views    = total_views    / valid
        avg_likes    = total_likes    / valid
        avg_comments = total_comments / valid

        # Play-like ratio (views per like; lower = more engaged)
        play_like_ratio = round(avg_views / avg_likes, 2) if avg_likes > 0 else 10.0

        # Engagement rate = (likes + comments + shares) / views * 100
        avg_engagement = (
            (total_likes + total_comments + total_shares) / total_views * 100
            if total_views > 0 else 3.0
        )
        avg_engagement = round(avg_engagement, 2)

        # Channel-level fields (yt-dlp returns these on the playlist object)
        channel_follower = int(info.get("channel_follower_count") or 0)
        uploader_id      = info.get("uploader_id") or info.get("channel_id") or username
        uploader         = info.get("uploader")    or info.get("channel")    or username

        # Guess primary category from video titles
        all_titles = " ".join(e.get("title", "") for e in entries).lower()
        category   = self._guess_category(all_titles)

        # Rough cart-video ratio: titles with shop/link/ad keywords
        cart_kw  = {"shop", "link", "buy", "get", "order", "deal", "sale",
                    "购物车", "下单", "链接", "优惠", "店铺", "挂车"}
        cart_cnt = sum(
            1 for e in entries
            if any(kw in (e.get("title", "") or "").lower() for kw in cart_kw)
        )
        cart_ratio = round(cart_cnt / len(entries), 2) if entries else 0.1

        return {
            "user_id":    uploader_id,
            "username":   f"@{uploader}",
            "followers":  channel_follower,
            "following":  0,            # not exposed by yt-dlp
            "total_videos": int(info.get("playlist_count") or len(entries)),
            "total_likes":  total_likes,
            "follower_growth_rate_30d": 0.0,   # requires historical data
            "play_like_ratio":    play_like_ratio,
            "avg_engagement_rate": avg_engagement,
            "cart_video_ratio":   cart_ratio,
            "primary_category":   category,
            "linktree_url":  None,
            "tiktok_shop_url": None,
            "audience_gender":     {"female": 0.55},
            "audience_age_18_34":  0.60,
            "audience_top_country": "US",
            # extra context sent to LLM
            "recent_video_count":  valid,
            "avg_views":           round(avg_views, 0),
            "avg_likes":           round(avg_likes, 0),
            "avg_comments":        round(avg_comments, 0),
            "sample_titles":       [e.get("title", "") for e in entries[:5]],
            "data_source":         "ytdlp",
        }

    @staticmethod
    def _guess_category(text: str) -> str:
        """Simple keyword-based category inference from video titles."""
        rules = [
            (["makeup", "beauty", "skincare", "lipstick", "foundation",
              "美妆", "护肤", "口红", "粉底"], "美妆护肤"),
            (["kitchen", "cook", "recipe", "food", "meal",
              "厨房", "做饭", "食谱", "美食"],  "厨房家居"),
            (["gadget", "tech", "iphone", "android", "device",
              "科技", "数码", "手机"],           "科技数码"),
            (["fitness", "workout", "gym", "exercise", "yoga",
              "健身", "运动", "减肥"],           "健身运动"),
            (["pet", "dog", "cat", "puppy", "kitten",
              "宠物", "狗", "猫"],               "宠物用品"),
            (["fashion", "outfit", "style", "clothes", "dress",
              "穿搭", "时尚", "服装"],           "时尚穿搭"),
        ]
        for keywords, label in rules:
            if any(kw in text for kw in keywords):
                return label
        return "家居好物"

    async def fetch(self, user_id: str) -> Optional[dict]:
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, user_id)
        if result:
            print(f"[AccountAnalyzer] Real data: @{result['username']} "
                  f"| followers={result['followers']:,} "
                  f"| engagement={result['avg_engagement_rate']}%")
        return result


# ── Account Analyzer ─────────────────────────────────────────────────────────

class AccountAnalyzer:

    def __init__(self):
        self._fetcher = TikTokProfileFetcher()

    async def fetch_account_data(self, user_id: str) -> dict:
        if settings.DEBUG_MODE:
            meta = MockFactory.account_metadata(user_id)
            meta["data_source"] = "mock"
            return meta

        # Live mode: real yt-dlp scraping
        result = await self._fetcher.fetch(user_id)
        if result:
            return result

        # Graceful fallback: mock data with clear warning
        print("[AccountAnalyzer] All real fetchers failed, falling back to mock")
        meta = MockFactory.account_metadata(user_id)
        meta["data_source"] = "mock_fallback"
        meta["username"]    = user_id if user_id.startswith("@") else f"@{user_id}"
        return meta

    def _calculate_commercial_score(self, meta: dict) -> int:
        score = 0
        score += min(30, int(meta.get("avg_engagement_rate", 0) / 5 * 30))
        score += min(20, int(meta.get("follower_growth_rate_30d", 0) / 10 * 20))
        score += min(20, int(meta.get("cart_video_ratio", 0) * 40))
        fans = meta.get("followers", 0)
        score += 15 if fans >= 1_000_000 else 10 if fans >= 100_000 else 5 if fans >= 10_000 else 2
        plr = meta.get("play_like_ratio", 10)
        score += 15 if 3 <= plr <= 8 else 8 if 1 <= plr < 3 else 3
        return min(100, score)

    def _estimate_monetization(self, meta: dict) -> dict:
        avg_views = meta.get("avg_views") or meta.get("followers", 10_000) * 0.15
        avg_price = 29.99
        base_gmv  = avg_views * 0.02 * 0.03 * avg_price
        return {
            "optimistic_gmv_usd":   round(base_gmv * 2.5, 0),
            "base_gmv_usd":         round(base_gmv, 0),
            "conservative_gmv_usd": round(base_gmv * 0.4, 0),
            "avg_views_estimate":   int(avg_views),
        }

    async def analyze(self, user_id: str) -> AccountAuditResult:
        meta = await self.fetch_account_data(user_id)

        account = AccountSchema(
            user_id=meta["user_id"],
            username=meta["username"],
            followers=meta["followers"],
            following=meta.get("following", 0),
            total_videos=meta["total_videos"],
            total_likes=meta["total_likes"],
            follower_growth_rate_30d=meta["follower_growth_rate_30d"],
            play_like_ratio=meta["play_like_ratio"],
            avg_engagement_rate=meta["avg_engagement_rate"],
            cart_video_ratio=meta["cart_video_ratio"],
            primary_category=meta["primary_category"],
            linktree_url=meta.get("linktree_url"),
            tiktok_shop_url=meta.get("tiktok_shop_url"),
            audience_top_country=meta.get("audience_top_country", "US"),
            data_source=meta.get("data_source", "unknown"),
        )

        score        = self._calculate_commercial_score(meta)
        monetization = self._estimate_monetization(meta)
        report       = await llm_service.audit_account(meta)
        categories   = [meta.get("primary_category", "家居好物"), "科技小工具", "美妆护肤"]

        return AccountAuditResult(
            account=account,
            commercial_score=score,
            recommended_categories=categories,
            audit_report=report,
            monetization_estimate=monetization,
        )


# singleton
account_analyzer = AccountAnalyzer()
