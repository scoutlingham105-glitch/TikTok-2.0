[README.md](https://github.com/user-attachments/files/26955773/README.md)
# TikTok 全链路决策引擎 v2.0 (TT-Intelligence)

> 从视频 URL 到利润精算的全流程闭环工具，支持 AI 自动化分析报告生成。

## 功能模块

| 模块 | 功能 | CLI 命令 | API 端点 |
|------|------|----------|----------|
| 视频拆解 | ASR/OCR + 钩子分析 + 分镜脚本 | `--type video --url` | `POST /api/v1/video/analyze` |
| 账号审计 | 互动指标 + 商业价值评分 + 变现预估 | `--type account --user` | `POST /api/v1/account/audit` |
| 产品精算 | 利润模型 + 趋势分析 + 选品评分 | `--type product --url --price` | `POST /api/v1/product/analyze` |

## 快速开始

### 1. 安装依赖

```bash
cd tt-intelligence
pip install -r requirements.txt
playwright install chromium  # Live 模式需要
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY（Mock 模式可跳过）
```

### 3. CLI 使用

```bash
# Mock 模式（无需任何 API 密钥，立即可用）
python main.py --mock --type video --url https://www.tiktok.com/@xxx/video/xxx
python main.py --mock --type account --user @beautyguru
python main.py --mock --type product --url https://amazon.com/dp/XXX --price 39.99
python main.py --mock --type product --img ./product.jpg --price 29.99

# 自定义物流费率（动态微调）
python main.py --mock --type product --url https://... --price 49.99 \
               --first-leg 10.5 --last-leg 6.0

# Live 模式（需要 OPENAI_API_KEY）
python main.py --type video --url https://www.tiktok.com/@xxx/video/xxx
```

### 4. 启动 Web API 服务

```bash
python main.py --serve --port 8080
# 访问文档：http://localhost:8080/docs
```

## 项目结构

```
tt-intelligence/
├── api/
│   └── routes.py          # FastAPI 路由定义
├── engine/
│   ├── video_parser.py    # 视频拆解（ASR/OCR + AI）
│   ├── account_analyzer.py # 账号画像与商业价值评估
│   └── product_expert.py  # 产品精算与选品分析
├── services/
│   └── llm_service.py     # Prompt 模板 + OpenAI 调用封装
├── utils/
│   ├── downloader.py      # 视频去水印下载
│   └── mock_factory.py    # Mock 数据生成器
├── config/
│   └── settings.py        # 全局配置（API KEY + 物流费率）
├── main.py                # CLI + FastAPI 启动入口
├── requirements.txt
└── .env.example
```

## 利润精算公式

```
净利润 = 售价
       - 采购成本
       - 头程运费（重量 × $12/kg）
       - 尾程运费（固定 $5/件）
       - 平台佣金（售价 × 8%）
       - 退货预留（毛利润 × 5%）
```

美国路向物流费率可在 `.env` 中动态调整，或通过 CLI `--first-leg` / `--last-leg` 参数覆盖。

## AI 降级机制

当 OpenAI API 不可用时，系统自动切换至**规则引擎**生成基础版分析报告：
- 视频分析：基于播赞比、赛道的规则判断
- 账号审计：基于多维指标加权评分
- 产品分析：基于利润率与趋势数据的量化输出

## 运行模式

- **Mock 模式** (`DEBUG_MODE=true`)：全程使用模拟数据，无需真实 API，适合开发与演示
- **Live 模式** (`DEBUG_MODE=false`)：接入真实 TikAPI / Apify / OpenAI，需配置相应密钥
