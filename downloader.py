"""
视频去水印下载模块
支持 TikTok 视频无水印下载，Live 模式通过 Playwright 模拟请求，
Mock 模式直接返回占位 URL
"""
import asyncio
import httpx
from typing import Optional
from config.settings import settings


async def fetch_no_watermark_url(video_url: str) -> Optional[str]:
    """
    获取 TikTok 视频的无水印直链

    策略优先级：
    1. TikAPI（若配置 TIKAPI_KEY）
    2. 公共去水印 API（snaptik 兼容接口）
    3. Mock 占位 URL（DEBUG_MODE）
    """
    if settings.DEBUG_MODE:
        return f"https://mock-cdn.tiktok.com/nowatermark/{video_url[-10:]}.mp4"

    # ── 尝试调用公共去水印接口 ─────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 使用 tiktok-api-dl 兼容接口（示例端点，可替换为自有服务）
            resp = await client.post(
                "https://api.tikwm.com/",
                data={"url": video_url, "count": 12, "cursor": 0, "hd": 1},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = resp.json()
            if data.get("code") == 0:
                return data["data"].get("play") or data["data"].get("hdplay")
    except Exception as exc:
        print(f"[downloader] 去水印接口失败: {exc}")

    return None


async def download_video(video_url: str, save_path: str = "/tmp/tiktok_video.mp4") -> str:
    """
    下载无水印视频到本地，返回本地文件路径
    Mock 模式下直接返回占位路径
    """
    if settings.DEBUG_MODE:
        return f"/tmp/mock_video_{video_url[-6:]}.mp4"

    direct_url = await fetch_no_watermark_url(video_url)
    if not direct_url:
        raise RuntimeError("无法获取无水印视频链接")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async with client.stream("GET", direct_url) as response:
            with open(save_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)

    return save_path
