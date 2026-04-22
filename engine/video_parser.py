"""
视频拆解模块 (Video Insights) - v2.2 修复版

修复历史：
  v2.1 - 接入 tikwm.com + yt-dlp subprocess（Windows 下 subprocess 找不到命令）
  v2.2 - 改用 yt_dlp Python 库 API；修复 Windows SSL；tikwm 多策略重试；详细诊断日志

数据获取优先级：
  1. tikwm.com API（免费公共接口，无需 Key，3 种请求策略轮试）
  2. yt-dlp Python API（pip install yt-dlp，跨平台，不依赖 PATH）
  3. Mock 降级（明确告警，不静默混入）
"""
import asyncio
import ssl
import httpx
import json
import io
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from config.settings import settings
from utils.mock_factory import MockFactory
from services.llm_service import llm_service


# ── Pydantic 数据模型 ────────────────────────────────────────────────────────

class VideoSchema(BaseModel):
    video_id: str
    url: str
    author: str
    publish_date: str
    duration_sec: int
    views: int
    likes: int
    comments: int
    shares: int
    transcription: str
    ocr_text: str
    track: str
    cover_url: Optional[str] = None
    music_title: Optional[str] = None
    product_link: Optional[str] = None
    data_source: str = "mock"       # tikwm / ytdlp / mock
    ai_analysis_report: Optional[str] = None


class VideoInsightsResult(BaseModel):
    video: VideoSchema
    analysis_report: str
    storyboard_scripts: Optional[str] = None


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _ts_to_date(ts) -> str:
    """时间戳安全转换为日期字符串"""
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return "未知"


def _make_ssl_context() -> ssl.SSLContext:
    """
    创建宽松的 SSL 上下文
    修复：Windows 系统证书链不完整时 httpx 报 SSL 验证错误（错误信息为空字符串）
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── tikwm 多策略抓取 ──────────────────────────────────────────────────────────

class TikwmFetcher:
    """
    tikwm.com 公共接口抓取器
    问题根因：Windows 上 httpx 默认 SSL 验证失败时返回空 Exception，容易漏诊
    修复：
      1. 禁用 SSL 验证（verify=False）
      2. 设置显式超时（connect/read 分开）
      3. 尝试 3 种 User-Agent / 参数组合
    """

    API_URL = "https://api.tikwm.com/"

    # 3 种请求策略，依次尝试
    _STRATEGIES = [
        # 策略 A：标准 POST form
        {
            "method": "post",
            "data": lambda url: {"url": url, "hd": 1},
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://tikwm.com/",
                "Accept": "application/json",
            },
        },
        # 策略 B：JSON body
        {
            "method": "post_json",
            "data": lambda url: {"url": url},
            "headers": {
                "User-Agent": "python-httpx/0.27",
                "Content-Type": "application/json",
            },
        },
        # 策略 C：GET 请求（部分地区 POST 被拦截）
        {
            "method": "get",
            "data": lambda url: {"url": url},
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36",
            },
        },
    ]

    async def fetch(self, url: str) -> Optional[dict]:
        for i, strategy in enumerate(self._STRATEGIES):
            result = await self._try_strategy(url, strategy, index=i + 1)
            if result:
                return result
        return None

    async def _try_strategy(self, url: str, strategy: dict, index: int) -> Optional[dict]:
        method   = strategy["method"]
        payload  = strategy["data"](url)
        headers  = strategy["headers"]

        try:
            # verify=False 解决 Windows SSL 证书链问题
            async with httpx.AsyncClient(
                verify=False,
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0),
                follow_redirects=True,
            ) as client:
                if method == "post":
                    resp = await client.post(self.API_URL, data=payload, headers=headers)
                elif method == "post_json":
                    resp = await client.post(self.API_URL, json=payload, headers=headers)
                else:  # get
                    resp = await client.get(self.API_URL, params=payload, headers=headers)

            data = resp.json()

        except httpx.HTTPStatusError as e:
            print(f"[tikwm] 策略{index} HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"[tikwm] 策略{index} 请求异常: {type(e).__name__}: {e}")
            return None

        if data.get("code") != 0 or not data.get("data"):
            msg = data.get("msg", "无错误信息")
            print(f"[tikwm] 策略{index} 接口返回异常: code={data.get('code')}, msg={msg}")
            return None

        print(f"[tikwm] ✅ 策略{index} 成功")
        return self._normalize(url, data["data"])

    def _normalize(self, url: str, d: dict) -> dict:
        """将 tikwm 响应归一化为统一的 meta 字典"""
        author = d.get("author", {})
        title  = (d.get("title", "") or "").strip()
        return {
            "video_id":    str(d.get("id", "unknown")),
            "url":         url,
            "author":      f"@{author.get('unique_id', 'unknown')} ({author.get('nickname', '')})",
            "publish_date": _ts_to_date(d.get("create_time", 0)),
            "duration_sec": int(d.get("duration", 0)),
            "views":       int(d.get("play", 0)),
            "likes":       int(d.get("digg", 0)),
            "comments":    int(d.get("comment", 0)),
            "shares":      int(d.get("share", 0)),
            "transcription": title or "（该视频无文字描述）",
            "ocr_text":    "",
            "cover_url":   d.get("cover", ""),
            "music_title": d.get("music_info", {}).get("title", ""),
            "track":       "",
            "product_link": None,
            "data_source": "tikwm",
        }


# ── yt-dlp Python API 抓取 ────────────────────────────────────────────────────

class YtdlpFetcher:
    """
    使用 yt_dlp Python 库（非 subprocess）抓取 TikTok 视频信息
    安装：pip install yt-dlp
    优势：跨平台，不依赖系统 PATH，可获取完整描述和字幕
    """

    def _run_sync(self, url: str) -> Optional[dict]:
        """同步执行 yt-dlp 提取（在线程池中调用）"""
        try:
            import yt_dlp  # 延迟导入，未安装时不崩溃
        except ImportError:
            print("[yt-dlp] 未安装，跳过（pip install yt-dlp 可启用）")
            return None

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            # 不验证 SSL（同 tikwm 修复方案）
            "nocheckcertificate": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"[yt-dlp] 提取失败: {type(e).__name__}: {e}")
            return None

        if not info:
            return None

        # 拼接所有可用文本内容
        title       = (info.get("title") or "").strip()
        description = (info.get("description") or "").strip()
        parts = [p for p in [title, description] if p]
        transcription = "\n".join(parts) if parts else "（无文字内容）"

        upload_date = info.get("upload_date", "")
        try:
            pub = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
        except Exception:
            pub = "未知"

        return {
            "video_id":     info.get("id", "unknown"),
            "url":          url,
            "author":       f"@{info.get('uploader_id', 'unknown')} ({info.get('uploader', '')})",
            "publish_date": pub,
            "duration_sec": int(info.get("duration") or 0),
            "views":        int(info.get("view_count") or 0),
            "likes":        int(info.get("like_count") or 0),
            "comments":     int(info.get("comment_count") or 0),
            "shares":       int(info.get("repost_count") or 0),
            "transcription": transcription,
            "ocr_text":     "",
            "cover_url":    info.get("thumbnail", ""),
            "music_title":  "",
            "track":        "",
            "product_link": None,
            "data_source":  "ytdlp",
        }

    async def fetch(self, url: str) -> Optional[dict]:
        """在线程池中执行同步抓取，避免阻塞事件循环"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_sync, url)
        if result:
            print(f"[yt-dlp] ✅ 抓取成功: {result['author']}")
        return result


# ── 主抓取协调器 ──────────────────────────────────────────────────────────────

class TikTokFetcher:
    """依次调用各策略，全部失败则返回带警告的 Mock 数据"""

    def __init__(self):
        self._tikwm  = TikwmFetcher()
        self._ytdlp  = YtdlpFetcher()

    async def fetch(self, url: str) -> dict:
        print(f"\n[VideoParser] 开始抓取: {url}")

        # 策略 1: tikwm.com（3 种子策略）
        result = await self._tikwm.fetch(url)
        if result:
            print(f"[VideoParser] ✅ tikwm 抓取成功 | 作者: {result['author']} | 播放: {result['views']:,}")
            return result

        # 策略 2: yt-dlp Python API
        print("[VideoParser] tikwm 全部失败，尝试 yt-dlp Python API...")
        result = await self._ytdlp.fetch(url)
        if result:
            print(f"[VideoParser] ✅ yt-dlp 抓取成功 | 作者: {result['author']}")
            return result

        # 策略 3: Mock 降级
        print("[VideoParser] ⚠️ 所有接口失败，降级为 Mock 数据")
        print("[VideoParser]    → 分析结果将与视频真实内容无关")
        print("[VideoParser]    → 请检查：1.网络是否正常 2.是否需要代理 3.pip install yt-dlp")
        mock = MockFactory.video_metadata(url)
        mock["data_source"] = "mock"
        mock["url"] = url
        mock["transcription"] = (
            f"⚠️ [数据获取失败] 无法抓取视频真实内容\n"
            f"原始链接: {url}\n"
            f"以下为模拟数据，AI 分析结果仅供参考，与该视频无关。\n\n"
            + mock["transcription"]
        )
        return mock


# ── 视频解析主引擎 ────────────────────────────────────────────────────────────

class VideoParser:

    def __init__(self):
        self._fetcher = TikTokFetcher()

    async def fetch_metadata(self, url: str) -> dict:
        if settings.DEBUG_MODE:
            print("[VideoParser] DEBUG_MODE=True，使用 Mock 数据（与视频内容无关）")
            mock = MockFactory.video_metadata(url)
            mock["data_source"] = "mock"
            mock["url"] = url
            return mock
        return await self._fetcher.fetch(url)

    async def parse(self, url: str) -> VideoInsightsResult:
        meta = await self.fetch_metadata(url)
        meta.setdefault("track", "待分析")

        video = VideoSchema(
            video_id=meta["video_id"],
            url=meta.get("url", url),
            author=meta["author"],
            publish_date=meta["publish_date"],
            duration_sec=meta["duration_sec"],
            views=meta["views"],
            likes=meta["likes"],
            comments=meta["comments"],
            shares=meta["shares"],
            transcription=meta["transcription"],
            ocr_text=meta.get("ocr_text", ""),
            track=meta.get("track", "待分析"),
            cover_url=meta.get("cover_url"),
            music_title=meta.get("music_title"),
            product_link=meta.get("product_link"),
            data_source=meta.get("data_source", "unknown"),
        )

        analysis = await llm_service.analyze_video(meta)
        video.ai_analysis_report = analysis

        return VideoInsightsResult(video=video, analysis_report=analysis)


# 全局单例
video_parser = VideoParser()
