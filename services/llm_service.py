"""
LLM 服务层 - 修复版
核心修复：
  1. 视频分析 Prompt 现在包含真实的视频 URL、标题、播放数据
  2. 明确区分"已获取真实内容"和"仅有基础元数据"两种情况
  3. 增加 OPENAI_BASE_URL 支持（兼容国内中转接口）
"""
import asyncio
from typing import Optional
from openai import AsyncOpenAI
from config.settings import settings
from utils.mock_factory import MockFactory


# ── Prompt 模板 ───────────────────────────────────────────────────────────────

VIDEO_ANALYSIS_PROMPT = """你是一位资深 TikTok 内容策略师，专注跨境电商爆款分析。

以下是从 TikTok 平台真实抓取的视频数据，请基于这些真实信息进行深度分析：

═══════════════ 视频真实数据 ═══════════════
原始链接：{url}
作者账号：{author}
发布时间：{publish_date}
视频时长：{duration_sec} 秒
背景音乐：{music_title}

【数据来源】{data_source_note}

【视频文案/标题/描述（真实内容）】
{transcription}

【互动数据】
- 播放量：{views:,}
- 点赞量：{likes:,}（点赞率 {like_rate:.2f}%）
- 评论数：{comments:,}
- 分享数：{shares:,}
═══════════════════════════════════════════

请严格基于以上真实数据完成以下分析（禁止编造与视频无关的内容）：

**1. 内容赛道判断**
根据视频标题和描述，判断属于哪个细分赛道（如：家居/美妆/科技/食品/宠物等），说明判断依据。

**2. 核心钩子（Hook）识别**
从标题/文案中提取最具吸引力的钩子句式，分析其类型（利益驱动/好奇心/痛点/共鸣）。

**3. 爆款底层逻辑**
结合播放量 {views:,}、点赞率 {like_rate:.2f}%、分享数 {shares:,}，分析该视频的传播逻辑：
- 数据表现如何？与同赛道平均水平对比
- 内容层：哪些元素促进了传播
- 情绪层：触发了用户什么情绪

**4. 高转化文案重写（3 组变体）**
基于原标题的核心卖点，重写 3 组 TikTok 风格高转化文案（A/B/C 版），每组附简短说明。

**5. 分镜脚本建议**
根据视频时长（{duration_sec}秒）和内容方向，输出分镜脚本表格：
| 镜号 | 时间区间 | 画面描述 | 旁白/字幕 | 情绪目标 |

用中文输出，分析须与视频真实内容紧密结合，不得泛泛而谈。"""


ACCOUNT_AUDIT_PROMPT = """你是一位跨境电商 TikTok 账号商业化顾问，专注账号变现策略。
请根据以下从 TikTok 平台真实抓取的账号数据，生成完整的商业价值评估报告：

【数据来源】{data_source_note}

【账号基础数据】
- 账号：{username}
- 粉丝数：{followers:,}
- 视频总数：{total_videos}
- 30日增粉率：{growth_rate}%（注：yt-dlp 无法获取历史数据时为 0，仅供参考）

【真实互动指标（基于最近 {recent_video_count} 条视频计算）】
- 平均播放量：{avg_views:,.0f}
- 平均点赞量：{avg_likes:,.0f}
- 平均评论数：{avg_comments:,.0f}
- 平均互动率：{engagement_rate}%
- 播赞比（播放/点赞）：{play_like_ratio}
- 挂车/带货视频占比：{cart_ratio}%

【内容方向】
- 主力赛道（系统推断）：{category}
- 近期视频标题样本：
{sample_titles}

【受众信息】
- 主要受众地区：{country}

【分析任务】
1. **账号健康度评分**：基于以上真实数据，给出 0-100 分评分，逐项说明得分依据
2. **内容定位分析**：根据视频标题样本，判断该账号的内容风格、受众群体与消费能力
3. **最适合带货品类推荐**：推荐 Top3 品类，说明与该账号调性的匹配逻辑
4. **单条视频变现潜力**：基于平均播放量 {avg_views:,.0f}，预估 GMV（乐观/基准/保守三情景）
5. **账号优化建议**：针对薄弱指标给出 3-5 条具体可执行策略

请用中文输出，分析须结合视频标题样本等真实内容，禁止泛泛而谈。"""


PRODUCT_ANALYSIS_PROMPT = """你是一位跨境电商选品专家与供应链顾问，专注 TikTok Shop 爆款选品。

以下是从产品页面真实抓取的数据，请基于真实信息进行全维度分析：

【数据来源】{data_source_note}
【产品链接】{origin_url}

【产品基本信息】
- 产品名称：{product_name}
- 产品描述：{description}
- 售价（用户设定）：${selling_price}
- 预估采购价（售价20%估算，需自行核验）：${supplier_price}
- 预估重量：{weight}kg

【市场数据】
- Amazon 评分：{amazon_rating} | 评价数：{amazon_review_count}
- Amazon 月销估算：{amazon_monthly_sales}件（0 表示未获取到数据）
- Google 趋势热度：{google_trend_score}/100（趋势：{trend_direction}）

【利润精算结果】
- 净利润：${net_profit:.2f}（头程$12/kg，尾程$5/件，平台佣金8%）

【分析任务】
1. **产品判断**：根据产品名称和描述，判断该产品的实际用途、目标用户和核心卖点
2. **选品评分**：综合利润空间、市场需求、竞争程度，给出 0-10 分并逐项说明
3. **TikTok 内容策略**：推荐 3 种最适合该产品的视频内容形式，附具体拍摄思路
4. **供应链建议**：预估采购价仅为参考，给出 1688/速卖通搜索关键词及议价建议
5. **竞争风险分析**：基于评价数和评分，判断市场竞争程度，识别潜在风险
6. **利润优化方案**：给出提升净利润的 2-3 个具体建议

请用中文输出，分析须结合产品真实信息，禁止泛泛而谈。"""


# ── LLM 服务 ──────────────────────────────────────────────────────────────────

class LLMService:

    def __init__(self):
        # 支持自定义 base_url（国内中转 / 第三方兼容接口）
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        self._client = AsyncOpenAI(**client_kwargs)
        self._model = settings.OPENAI_MODEL

    async def _chat(self, prompt: str, system: str = "你是一位专业的 TikTok 跨境电商分析师。") -> str:
        response = await asyncio.wait_for(
            self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
            ),
            timeout=90,
        )
        return response.choices[0].message.content

    async def analyze_video(self, meta: dict) -> str:
        """
        视频深度拆解分析
        关键修复：使用 meta 中的真实字段（url、transcription、views 等）填充 Prompt
        不再使用任何随机或模拟数据
        """
        try:
            views = meta.get("views", 0)
            likes = meta.get("likes", 0)
            like_rate = (likes / views * 100) if views > 0 else 0.0

            # 数据来源说明（告知 LLM 数据可信度）
            data_source = meta.get("data_source", "unknown")
            if data_source == "tikwm":
                source_note = "✅ 通过 tikwm.com 真实抓取（标题/描述为视频原始文案）"
            elif data_source == "ytdlp":
                source_note = "✅ 通过 yt-dlp 真实抓取（含完整描述/字幕）"
            else:
                source_note = "⚠️ 模拟数据（真实接口不可用，分析仅供参考）"

            prompt = VIDEO_ANALYSIS_PROMPT.format(
                url=meta.get("url", "未知"),
                author=meta.get("author", "未知"),
                publish_date=meta.get("publish_date", "未知"),
                duration_sec=meta.get("duration_sec", 0),
                music_title=meta.get("music_title") or "未知",
                data_source_note=source_note,
                transcription=meta.get("transcription", "（无文案内容）"),
                views=views,
                likes=likes,
                like_rate=like_rate,
                comments=meta.get("comments", 0),
                shares=meta.get("shares", 0),
            )
            return await self._chat(prompt)

        except Exception as exc:
            print(f"[LLMService] 视频分析失败: {exc}，启用规则引擎降级")
            return MockFactory.fallback_video_report(meta)

    async def audit_account(self, meta: dict) -> str:
        try:
            data_source = meta.get("data_source", "unknown")
            if data_source == "ytdlp":
                source_note = "yt-dlp 真实抓取账号主页（最近视频数据）"
            elif data_source == "mock_fallback":
                source_note = "真实接口失败，以下为模拟数据，仅供参考"
            else:
                source_note = "模拟数据（DEBUG_MODE=True）"

            sample_titles = meta.get("sample_titles", [])
            titles_str = "\n".join(f"  - {t}" for t in sample_titles) if sample_titles else "  （无样本）"

            prompt = ACCOUNT_AUDIT_PROMPT.format(
                data_source_note=source_note,
                username=meta.get("username", "N/A"),
                followers=int(meta.get("followers", 0)),
                total_videos=meta.get("total_videos", 0),
                growth_rate=meta.get("follower_growth_rate_30d", 0),
                recent_video_count=meta.get("recent_video_count", 0),
                avg_views=float(meta.get("avg_views", 0)),
                avg_likes=float(meta.get("avg_likes", 0)),
                avg_comments=float(meta.get("avg_comments", 0)),
                engagement_rate=meta.get("avg_engagement_rate", 0),
                play_like_ratio=meta.get("play_like_ratio", 0),
                cart_ratio=int(meta.get("cart_video_ratio", 0) * 100),
                category=meta.get("primary_category", "未知"),
                sample_titles=titles_str,
                country=meta.get("audience_top_country", "US"),
            )
            return await self._chat(prompt)
        except Exception as exc:
            print(f"[LLMService] 账号分析失败: {exc}，启用规则引擎降级")
            return MockFactory.fallback_account_report(meta)

    async def analyze_product(self, meta: dict, net_profit: float) -> str:
        try:
            data_source = meta.get("data_source", "unknown")
            if data_source == "scraped":
                source_note = "httpx 真实抓取产品页面（标题/描述/评分为真实数据）"
            elif data_source == "mock_fallback":
                source_note = "页面抓取失败，以下为模拟数据，仅供参考"
            else:
                source_note = "模拟数据（DEBUG_MODE=True）"

            prompt = PRODUCT_ANALYSIS_PROMPT.format(
                data_source_note=source_note,
                origin_url=meta.get("origin_url", "未知"),
                product_name=meta.get("product_name", "未知产品"),
                description=meta.get("description", "（无描述）")[:200],
                selling_price=meta.get("selling_price_usd", 0),
                supplier_price=meta.get("supplier_price_usd", 0),
                weight=meta.get("weight_kg", 0),
                net_profit=net_profit,
                amazon_rating=meta.get("amazon_rating", 0),
                amazon_review_count=meta.get("amazon_review_count", 0),
                amazon_monthly_sales=meta.get("amazon_monthly_sales", 0),
                google_trend_score=meta.get("google_trend_score", 0),
                trend_direction=meta.get("trend_direction", "未知"),
            )
            return await self._chat(prompt)
        except Exception as exc:
            print(f"[LLMService] 产品分析失败: {exc}，启用规则引擎降级")
            return MockFactory.fallback_product_report(meta, net_profit)

    async def generate_scripts(self, product_name: str, style: str = "开箱测评") -> str:
        prompt = (
            f"请为产品《{product_name}》生成一条 TikTok {style}风格视频脚本，"
            f"包含：钩子话术、产品介绍、痛点解决、行动号召（CTA），"
            f"并输出详细分镜脚本表格（Markdown 格式）。用中文输出。"
        )
        try:
            return await self._chat(prompt)
        except Exception as exc:
            return f"脚本生成失败（{exc}），请检查 API 配置后重试。"


# 全局单例
llm_service = LLMService()
