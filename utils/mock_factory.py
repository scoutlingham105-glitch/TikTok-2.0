"""
模拟数据生成工厂
在 DEBUG_MODE=True 时，替代真实 API 调用，确保无网络环境下业务逻辑完整跑通
"""
import random
import uuid
from datetime import datetime, timedelta
from typing import Any


def _random_date(days_back: int = 365) -> str:
    """生成随机过去日期字符串"""
    dt = datetime.now() - timedelta(days=random.randint(0, days_back))
    return dt.strftime("%Y-%m-%d")


class MockFactory:
    """所有模块的 Mock 数据集中生成器"""

    # ── 视频元数据 ─────────────────────────────────────────────────────────
    @staticmethod
    def video_metadata(url: str = "") -> dict[str, Any]:
        authors = ["@beautyqueen_us", "@gadgetguru99", "@homehackpro", "@fitnessjane"]
        hooks = [
            "你知道这个产品可以让你省下 50% 的时间吗？",
            "我发现了一个改变生活的小技巧，竟然才 $9.99！",
            "TikTok 上最火的厨房神器，今天终于入手了！",
            "三十秒教你用这个工具搞定所有人！",
        ]
        tracks = ["家居好物", "美妆护肤", "科技小工具", "健身器材", "宠物用品"]
        return {
            "video_id": str(uuid.uuid4())[:8],
            "url": url or f"https://www.tiktok.com/@mock/video/{random.randint(10**15, 10**16)}",
            "author": random.choice(authors),
            "publish_date": _random_date(30),
            "duration_sec": random.randint(15, 60),
            "views": random.randint(50_000, 5_000_000),
            "likes": random.randint(1_000, 500_000),
            "comments": random.randint(50, 10_000),
            "shares": random.randint(100, 50_000),
            "transcription": (
                f"【Hook】{random.choice(hooks)} "
                "产品真的太好用了，已经回购三次了。这个月销量直接破了一万单。"
                "评论区大家都在问链接，直接挂车里了，点击购物车即可下单。"
                "限时优惠今天结束，不要错过！"
            ),
            "ocr_text": f"{random.choice(tracks)} 爆款 | 限时特惠 | 点击购物车",
            "track": random.choice(tracks),
            "product_link": f"https://www.tiktok.com/shop/mock/{random.randint(1000, 9999)}",
        }

    # ── 账号数据 ───────────────────────────────────────────────────────────
    @staticmethod
    def account_metadata(user_id: str = "") -> dict[str, Any]:
        categories = ["家居好物", "美妆护肤", "科技小工具"]
        follower_base = random.randint(10_000, 2_000_000)
        return {
            "user_id": user_id or f"user_{random.randint(1000, 9999)}",
            "username": f"@mock_{random.randint(100, 999)}",
            "followers": follower_base,
            "following": random.randint(100, 5_000),
            "total_videos": random.randint(20, 500),
            "total_likes": follower_base * random.uniform(5, 30),
            # 关键指标
            "follower_growth_rate_30d": round(random.uniform(0.5, 15.0), 2),  # 近30日增粉率 %
            "play_like_ratio": round(random.uniform(3.0, 12.0), 2),           # 播赞比
            "avg_engagement_rate": round(random.uniform(1.5, 8.0), 2),        # 平均互动率 %
            "cart_video_ratio": round(random.uniform(0.1, 0.8), 2),           # 挂车视频占比
            "primary_category": random.choice(categories),
            "linktree_url": f"https://linktr.ee/mock_{random.randint(100, 999)}",
            "tiktok_shop_url": f"https://shop.tiktok.com/@mock_{random.randint(100, 999)}",
            "top_videos": [MockFactory.video_metadata() for _ in range(3)],
            "audience_gender": {"female": round(random.uniform(0.4, 0.75), 2)},
            "audience_age_18_34": round(random.uniform(0.45, 0.72), 2),
            "audience_top_country": "US",
        }

    # ── 产品与供应商数据 ────────────────────────────────────────────────────
    @staticmethod
    def product_metadata(origin_url: str = "", selling_price: float = 29.99) -> dict[str, Any]:
        names = [
            "便携式硅胶折叠碗套装", "多功能厨房计时器收纳架",
            "USB 充电颈椎按摩仪", "智能感应皂液器",
            "猫咪自动喂食器（定时款）",
        ]
        suppliers = ["义乌好货源", "广州美货汇", "深圳科技直供", "1688严选工厂"]
        return {
            "product_id": str(uuid.uuid4())[:8],
            "origin_url": origin_url or f"https://www.amazon.com/dp/MOCK{random.randint(1000, 9999)}",
            "product_name": random.choice(names),
            "supplier": random.choice(suppliers),
            "supplier_price_usd": round(random.uniform(1.5, 8.0), 2),       # 采购成本
            "weight_kg": round(random.uniform(0.1, 1.5), 2),                 # 重量
            "selling_price_usd": selling_price,                              # 售价
            "amazon_rating": round(random.uniform(3.8, 4.9), 1),
            "amazon_review_count": random.randint(50, 5000),
            "amazon_monthly_sales": random.randint(200, 10_000),
            "google_trend_score": random.randint(40, 95),                    # 谷歌趋势热度 0-100
            "trend_direction": random.choice(["上升", "稳定", "下降"]),
            "earliest_viral_date": _random_date(180),
            "viral_platform": random.choice(["TikTok", "Instagram Reels", "YouTube Shorts"]),
            "recent_amazon_reviews": [
                "Quality is amazing for the price! Will buy again.",
                "Arrived quickly, exactly as described.",
                "My kids love it. Great gift idea.",
                "Broke after 2 weeks, not happy.",
                "Exceeded expectations, highly recommend!",
            ],
        }

    # ── AI 分析报告（规则引擎降级版）────────────────────────────────────────
    @staticmethod
    def fallback_video_report(meta: dict) -> str:
        """AI 调用失败时，基于规则生成基础版视频分析报告"""
        views = meta.get("views", 0)
        likes = meta.get("likes", 0)
        play_like = round(likes / views * 100, 2) if views else 0
        return (
            f"【基础版分析报告（规则引擎）】\n"
            f"视频 ID: {meta.get('video_id', 'N/A')}\n"
            f"播放量: {views:,} | 点赞率: {play_like}%\n"
            f"赛道判断: {meta.get('track', '未知')}\n"
            f"钩子类型: 利益驱动型（价格锚点 + 痛点呈现）\n"
            f"变现潜力: {'高' if play_like > 5 else '中' if play_like > 2 else '低'}\n"
            f"建议：提升前3秒视觉冲击力，增加 CTA 引导频次。\n"
            f"（注：AI 接口不可用，以上为规则引擎输出，精度有限）"
        )

    @staticmethod
    def fallback_account_report(meta: dict) -> str:
        """账号分析降级报告"""
        score = min(100, int(
            meta.get("avg_engagement_rate", 3) * 10 +
            meta.get("cart_video_ratio", 0.3) * 30 +
            meta.get("follower_growth_rate_30d", 2) * 2
        ))
        return (
            f"【基础版账号报告（规则引擎）】\n"
            f"账号: {meta.get('username', 'N/A')} | 粉丝: {meta.get('followers', 0):,}\n"
            f"互动率: {meta.get('avg_engagement_rate', 0)}% | 挂车比: {int(meta.get('cart_video_ratio', 0)*100)}%\n"
            f"商业价值评分: {score}/100\n"
            f"推荐带货品类: {meta.get('primary_category', '家居好物')}\n"
            f"（注：AI 接口不可用，以上为规则引擎输出）"
        )

    @staticmethod
    def fallback_product_report(meta: dict, net_profit: float) -> str:
        """产品分析降级报告"""
        roi = net_profit / meta.get("supplier_price_usd", 1) * 100
        return (
            f"【基础版产品报告（规则引擎）】\n"
            f"产品: {meta.get('product_name', 'N/A')}\n"
            f"售价: ${meta.get('selling_price_usd', 0):.2f} | 采购: ${meta.get('supplier_price_usd', 0):.2f}\n"
            f"净利润: ${net_profit:.2f} | ROI: {roi:.1f}%\n"
            f"谷歌趋势: {meta.get('google_trend_score', 0)}/100 ({meta.get('trend_direction', '未知')})\n"
            f"最早爆发: {meta.get('earliest_viral_date', 'N/A')} 于 {meta.get('viral_platform', 'N/A')}\n"
            f"（注：AI 接口不可用，以上为规则引擎输出）"
        )
