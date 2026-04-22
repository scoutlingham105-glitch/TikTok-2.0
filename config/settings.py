"""
配置管理模块
核心修复：DEBUG_MODE 默认改为 False（生产模式），确保默认走真实数据抓取
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ── AI 接口配置 ──────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="sk-mock-key", env="OPENAI_API_KEY")
    # 支持国内中转接口，如 https://api.moonshot.cn/v1 或其他兼容 OpenAI 的接口
    OPENAI_BASE_URL: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")
    OPENAI_MODEL: str = Field(default="gpt-4o", env="OPENAI_MODEL")

    # ── TikTok 数据接口（可选，tikwm 无需配置 Key）─────────────────────────
    TIKAPI_KEY: Optional[str] = Field(default=None, env="TIKAPI_KEY")
    APIFY_TOKEN: Optional[str] = Field(default=None, env="APIFY_TOKEN")

    # ── 运行模式 ────────────────────────────────────────────────────────────
    # ⚠️ 重要修复：默认改为 False（Live 模式），True 才使用 Mock 数据
    # Mock 模式下视频分析与真实链接内容无关，仅用于开发调试
    DEBUG_MODE: bool = Field(default=False, env="DEBUG_MODE")

    # ── 物流费率模板（美国路向，单位：USD）──────────────────────────────────
    FIRST_LEG_FEE_PER_KG: float = 12.0
    LAST_LEG_FEE_PER_UNIT: float = 5.0
    PLATFORM_FEE_RATE: float = 0.08
    RETURN_RATE: float = 0.05

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
