"""
FastAPI 路由定义 - 修复版
核心修复：接收前端 mock 参数后，动态更新运行时设置，确保 Live/Mock 模式正确切换
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import tempfile
import os

import traceback
from config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["TT-Intelligence"])


# ── 请求模型 ──────────────────────────────────────────────────────────────────

class VideoAnalyzeRequest(BaseModel):
    url: str
    mock: bool = False   # 修复：默认 False，使用真实数据

class AccountAuditRequest(BaseModel):
    user_id: str
    mock: bool = False

class ProductAnalyzeRequest(BaseModel):
    origin_url: str
    selling_price: float
    first_leg_rate: Optional[float] = None
    last_leg_fee: Optional[float] = None

class ProfitCalcRequest(BaseModel):
    selling_price: float
    purchase_cost: float
    weight_kg: float
    first_leg_rate: Optional[float] = None
    last_leg_fee: Optional[float] = None
    platform_fee_rate: Optional[float] = None


def _apply_mock_mode(mock: bool):
    """
    运行时动态切换 DEBUG_MODE
    修复：之前 settings 单例在进程启动时已固化，需要直接修改实例属性
    """
    settings.DEBUG_MODE = mock


# ── 视频拆解接口 ──────────────────────────────────────────────────────────────

@router.post("/video/analyze", summary="视频深度拆解分析")
async def analyze_video(req: VideoAnalyzeRequest):
    """
    输入 TikTok 视频 URL，返回真实视频数据 + AI 深度分析
    Live 模式（mock=false）：通过 tikwm.com 真实抓取视频标题/播放量/点赞等
    Mock 模式（mock=true）：使用模拟数据（结果与视频内容无关，仅用于测试）
    """
    _apply_mock_mode(req.mock)

    # 延迟导入，确保 settings.DEBUG_MODE 已更新后再初始化
    from engine.video_parser import VideoParser
    parser = VideoParser()

    try:
        result = await parser.parse(req.url)
        return {
            "status": "success",
            "data_source": result.video.data_source,
            "video": result.video.model_dump(),
            "analysis_report": result.analysis_report,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"视频分析失败: {str(e)}")


# ── 账号审计接口 ──────────────────────────────────────────────────────────────

@router.post("/account/audit", summary="账号商业价值评估")
async def audit_account(req: AccountAuditRequest):
    _apply_mock_mode(req.mock)
    from engine.account_analyzer import AccountAnalyzer
    analyzer = AccountAnalyzer()
    try:
        result = await analyzer.analyze(req.user_id)
        return {
            "status": "success",
            "account": result.account.model_dump(),
            "commercial_score": result.commercial_score,
            "recommended_categories": result.recommended_categories,
            "monetization_estimate": result.monetization_estimate,
            "audit_report": result.audit_report,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"账号审计失败: {str(e)}")


# ── 产品精算接口 ──────────────────────────────────────────────────────────────

@router.post("/product/analyze", summary="产品选品分析与利润精算")
async def analyze_product(req: ProductAnalyzeRequest):
    from engine.product_expert import ProductExpert
    expert = ProductExpert()
    try:
        result = await expert.analyze(
            origin_url=req.origin_url,
            selling_price=req.selling_price,
            first_leg_rate=req.first_leg_rate,
            last_leg_fee=req.last_leg_fee,
        )
        return {
            "status": "success",
            "product": result.product.model_dump(),
            "profit_model": result.profit_model.model_dump(),
            "selection_score": result.selection_score,
            "analysis_report": result.analysis_report,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"产品分析失败: {str(e)}")


@router.post("/product/profit-calc", summary="快速利润精算（单品）")
async def quick_profit_calc(req: ProfitCalcRequest):
    from engine.product_expert import ProfitCalculator
    calc = ProfitCalculator()
    try:
        result = calc.calculate(
            selling_price=req.selling_price,
            purchase_cost=req.purchase_cost,
            weight_kg=req.weight_kg,
            first_leg_rate=req.first_leg_rate,
            last_leg_fee=req.last_leg_fee,
            platform_fee_rate=req.platform_fee_rate,
        )
        return {"status": "success", "profit_model": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/product/analyze-image", summary="图片识别产品分析")
async def analyze_product_image(
    image: UploadFile = File(...),
    selling_price: float = Form(default=29.99),
):
    from engine.product_expert import ProductExpert
    expert = ProductExpert()
    try:
        suffix = os.path.splitext(image.filename or "img.jpg")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await image.read())
            tmp_path = tmp.name

        result = await expert.analyze(
            origin_url=f"image://{image.filename}",
            selling_price=selling_price,
            image_path=tmp_path,
        )
        os.unlink(tmp_path)

        return {
            "status": "success",
            "product": result.product.model_dump(),
            "profit_model": result.profit_model.model_dump(),
            "selection_score": result.selection_score,
            "analysis_report": result.analysis_report,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"图片分析失败: {str(e)}")


# ── 系统状态接口 ──────────────────────────────────────────────────────────────

@router.get("/health", summary="系统健康检查")
async def health_check():
    return {
        "status": "healthy",
        "debug_mode": settings.DEBUG_MODE,
        "model": settings.OPENAI_MODEL,
        "base_url": settings.OPENAI_BASE_URL or "默认 OpenAI",
        "version": "2.1.0",
        "tikwm_note": "视频数据通过 tikwm.com 免费接口获取，无需 API Key",
    }
