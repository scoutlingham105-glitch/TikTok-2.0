"""
TikTok 全链路分析工具 (TT-Intelligence) v2.0
程序启动入口：支持 CLI 命令行调用 + FastAPI Web 服务

CLI 使用示例：
  python main.py --type video --url https://www.tiktok.com/@xxx/video/xxx
  python main.py --type account --user @beautyguru
  python main.py --type product --img ./product.jpg --price 29.99
  python main.py --type product --url https://amazon.com/dp/XXX --price 39.99
  python main.py --serve  # 启动 FastAPI 服务器
  python main.py --mock --type video --url https://tiktok.com/...  # Mock 模式
"""
import asyncio
import argparse
import json
import sys
import os
from typing import Optional

# ── 确保模块路径正确 ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup_rich_console():
    """初始化 Rich 终端美化工具"""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.markdown import Markdown
        from rich.table import Table
        return Console(), Panel, Markdown, Table
    except ImportError:
        return None, None, None, None


console, Panel, Markdown, Table = _setup_rich_console()


def _print(msg: str, style: str = ""):
    """统一输出方法（有 Rich 用 Rich，无则 print）"""
    if console:
        console.print(msg, style=style)
    else:
        print(msg)


def _print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║        TikTok 全链路决策引擎 v2.0 (TT-Intelligence)       ║
║   Video · Account · Product · Profit · AI Automation    ║
╚══════════════════════════════════════════════════════════╝
"""
    _print(banner, style="bold cyan")


def _print_profit_table(profit_model: dict):
    """格式化输出利润精算表格"""
    if Table and console:
        table = Table(title="💰 利润精算明细", show_header=True, header_style="bold green")
        table.add_column("项目", style="cyan", width=20)
        table.add_column("金额（USD）", style="yellow", justify="right")

        table.add_row("售价", f"${profit_model['selling_price']:.2f}")
        table.add_row("采购成本", f"-${profit_model['purchase_cost']:.2f}")
        table.add_row("头程运费", f"-${profit_model['first_leg_cost']:.2f}")
        table.add_row("尾程运费", f"-${profit_model['last_leg_cost']:.2f}")
        table.add_row("平台佣金", f"-${profit_model['platform_fee']:.2f}")
        table.add_row("退货预留", f"-${profit_model['return_reserve']:.2f}")
        table.add_row("─" * 15, "─" * 10)
        table.add_row(
            "[bold]净利润[/bold]",
            f"[bold green]${profit_model['net_profit']:.2f}[/bold green]"
            if profit_model['net_profit'] > 0
            else f"[bold red]${profit_model['net_profit']:.2f}[/bold red]"
        )
        table.add_row("ROI", f"{profit_model['roi_pct']:.1f}%")
        table.add_row("盈亏平衡价", f"${profit_model['breakeven_price']:.2f}")
        console.print(table)
    else:
        print(json.dumps(profit_model, indent=2, ensure_ascii=False))


# ── 各模块 CLI 处理函数 ────────────────────────────────────────────────────────

async def run_video_analysis(url: str, mock: bool = True):
    """执行视频拆解分析"""
    from config.settings import settings
    if mock:
        os.environ["DEBUG_MODE"] = "true"

    from engine.video_parser import video_parser

    _print(f"\n🎬 开始分析视频：{url}", style="bold blue")
    _print("⏳ 正在获取数据并调用 AI 分析...\n", style="dim")

    result = await video_parser.parse(url)

    # 输出元数据摘要
    v = result.video
    _print(f"📊 视频基础数据", style="bold")
    _print(f"   ID: {v.video_id} | 作者: {v.author} | 赛道: {v.track}")
    _print(f"   播放: {v.views:,} | 点赞: {v.likes:,} | 评论: {v.comments:,} | 分享: {v.shares:,}")
    _print(f"   发布时间: {v.publish_date}\n")

    # 输出 AI 分析报告
    _print("─" * 60)
    _print("🤖 AI 深度分析报告", style="bold green")
    _print("─" * 60)
    if Markdown and console:
        console.print(Markdown(result.analysis_report))
    else:
        print(result.analysis_report)


async def run_account_audit(user_id: str, mock: bool = True):
    """执行账号商业价值评估"""
    if mock:
        os.environ["DEBUG_MODE"] = "true"

    from engine.account_analyzer import account_analyzer

    _print(f"\n👤 开始审计账号：{user_id}", style="bold blue")
    _print("⏳ 正在分析账号数据...\n", style="dim")

    result = await account_analyzer.analyze(user_id)

    # 输出账号指标摘要
    a = result.account
    _print(f"📊 账号核心指标", style="bold")
    _print(f"   账号: {a.username} | 粉丝: {a.followers:,}")
    _print(f"   30日增粉率: {a.follower_growth_rate_30d}% | 互动率: {a.avg_engagement_rate}%")
    _print(f"   播赞比: {a.play_like_ratio} | 挂车比: {int(a.cart_video_ratio*100)}%")
    _print(f"   商业价值评分: [bold yellow]{result.commercial_score}/100[/bold yellow]" if console else f"   商业价值评分: {result.commercial_score}/100")

    # 变现预估
    me = result.monetization_estimate
    _print(f"\n💵 单条视频 GMV 预估（美元）", style="bold")
    _print(f"   乐观: ${me['optimistic_gmv_usd']:,.0f} | 基准: ${me['base_gmv_usd']:,.0f} | 保守: ${me['conservative_gmv_usd']:,.0f}")

    # AI 报告
    _print("\n" + "─" * 60)
    _print("🤖 AI 账号审计报告", style="bold green")
    _print("─" * 60)
    if Markdown and console:
        console.print(Markdown(result.audit_report))
    else:
        print(result.audit_report)


async def run_product_analysis(
    origin_url: str,
    selling_price: float,
    image_path: Optional[str] = None,
    mock: bool = True,
    first_leg_rate: Optional[float] = None,
    last_leg_fee: Optional[float] = None,
):
    """执行产品选品分析与利润精算"""
    if mock:
        os.environ["DEBUG_MODE"] = "true"

    from engine.product_expert import product_expert

    source = image_path or origin_url
    _print(f"\n🛍️  开始分析产品：{source}", style="bold blue")
    _print(f"   售价：${selling_price:.2f}\n", style="dim")

    result = await product_expert.analyze(
        origin_url=origin_url,
        selling_price=selling_price,
        image_path=image_path,
        first_leg_rate=first_leg_rate,
        last_leg_fee=last_leg_fee,
    )

    # 产品信息
    p = result.product
    _print(f"📦 产品信息", style="bold")
    _print(f"   名称: {p.product_name}")
    _print(f"   供应商: {p.supplier} | 采购价: ${p.supplier_price_usd:.2f} | 重量: {p.weight_kg}kg")
    _print(f"   Amazon评分: {p.amazon_rating} | 月销量: {p.amazon_monthly_sales:,}")
    _print(f"   Google趋势: {p.google_trend_score}/100 ({p.trend_direction})")
    _print(f"   选品评分: [bold yellow]{result.selection_score}/10[/bold yellow]\n" if console else f"   选品评分: {result.selection_score}/10\n")

    # 利润精算表格
    _print_profit_table(result.profit_model.model_dump())

    # AI 报告
    _print("\n" + "─" * 60)
    _print("🤖 AI 产品分析报告", style="bold green")
    _print("─" * 60)
    if Markdown and console:
        console.print(Markdown(result.analysis_report))
    else:
        print(result.analysis_report)


# ── CLI 入口 ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tt-intelligence",
        description="TikTok 全链路决策引擎 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py --type video --url https://www.tiktok.com/@xxx/video/xxx
  python main.py --type account --user @beautyguru
  python main.py --type product --url https://amazon.com/dp/XXX --price 39.99
  python main.py --type product --img ./product.jpg --price 29.99
  python main.py --serve           # 启动 API 服务器（端口 8080）
  python main.py --mock --type video --url ...  # 强制 Mock 模式
        """,
    )

    parser.add_argument("--type", choices=["video", "account", "product"], help="分析类型")
    parser.add_argument("--url", type=str, help="视频或产品 URL")
    parser.add_argument("--user", type=str, help="TikTok 账号 ID")
    parser.add_argument("--img", type=str, help="产品图片路径（本地文件）")
    parser.add_argument("--price", type=float, default=29.99, help="产品售价（USD）")
    parser.add_argument("--first-leg", type=float, help="自定义头程费率（$/kg）")
    parser.add_argument("--last-leg", type=float, help="自定义尾程费用（$/件）")
    parser.add_argument("--mock", action="store_true", help="启用 Mock 模式（无需真实 API）")
    parser.add_argument("--serve", action="store_true", help="启动 FastAPI Web 服务")
    parser.add_argument("--port", type=int, default=8080, help="FastAPI 服务端口（默认 8080）")
    parser.add_argument("--output", choices=["json", "pretty"], default="pretty", help="输出格式")

    return parser


async def start_server(port: int = 8080):
    """启动 FastAPI 服务（异步版本，避免事件循环冲突）"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import os
    from uvicorn.config import Config
    from uvicorn.server import Server
    from api.routes import router

    app = FastAPI(
        title="TT-Intelligence API",
        description="TikTok 全链路分析工具接口文档",
        version="2.0.0",
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # 开发环境，生产请替换为具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静态文件托管
    frontend_path = "frontend"
    if os.path.exists(frontend_path):
        app.mount("/static", StaticFiles(directory=frontend_path), name="static")
        @app.get("/")
        async def serve_index():
            index_file = os.path.join(frontend_path, "index.html")
            if os.path.exists(index_file):
                return FileResponse(index_file)
            return {"message": "Frontend not found"}

    # 注册 API 路由
    app.include_router(router)

    _print(f"\n🚀 启动 TT-Intelligence API 服务", style="bold green")
    _print(f"   地址: http://localhost:{port}")
    _print(f"   文档: http://localhost:{port}/docs")
    _print(f"   前端: http://localhost:{port}/ (如果存在 frontend/index.html)")
    _print(f"   健康: http://localhost:{port}/api/v1/health\n")

    # 异步启动 uvicorn 服务器
    config = Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config=config)
    await server.serve()


async def main():
    _print_banner()
    parser = build_parser()
    args = parser.parse_args()

    # ── 启动 Web 服务模式 ──────────────────────────────────────────────────
    if args.serve:
        await start_server(args.port)  # ✅ 正确等待
        return

    # ── CLI 分析模式 ───────────────────────────────────────────────────────
    if not args.type:
        parser.print_help()
        return

    use_mock = args.mock or os.getenv("DEBUG_MODE", "true").lower() == "true"

    if args.type == "video":
        if not args.url:
            _print("❌ 请提供 --url 参数", style="bold red")
            sys.exit(1)
        await run_video_analysis(args.url, mock=use_mock)

    elif args.type == "account":
        if not args.user:
            _print("❌ 请提供 --user 参数", style="bold red")
            sys.exit(1)
        await run_account_audit(args.user, mock=use_mock)

    elif args.type == "product":
        if not args.url and not args.img:
            _print("❌ 请提供 --url 或 --img 参数", style="bold red")
            sys.exit(1)
        await run_product_analysis(
            origin_url=args.url or f"image://{args.img}",
            selling_price=args.price,
            image_path=args.img,
            mock=use_mock,
            first_leg_rate=args.first_leg,
            last_leg_fee=args.last_leg,
        )


if __name__ == "__main__":
    asyncio.run(main())
