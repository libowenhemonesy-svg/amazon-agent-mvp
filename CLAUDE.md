# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Amazon Agent 运营台 — AI 驱动的跨境电商运营分析平台。后端 FastAPI + SQLAlchemy，前端 Vanilla JS SPA，AI 用 LangGraph + DeepSeek。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器（默认端口 8010）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload

# 运行测试
pytest

# 运行单个测试
pytest tests/test_metrics.py::test_function_name

# Alembic 数据库迁移（生产用 PostgreSQL）
alembic upgrade head
alembic revision --autogenerate -m "描述"
```

## 环境变量

必须配置 `.env` 文件（从 `.env.example` 复制）。关键变量：

- `LLM_PROVIDER=deepseek` — AI 功能必需
- `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL` — DeepSeek API 配置
- `DATABASE_URL` — 默认 `sqlite+pysqlite:///./amazon_agent.db`，生产用 PostgreSQL
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET` — 飞书同步（可选）

## 架构概览

### 数据流

CSV/Excel 导入 → `app/importers/tabular.py` 解析 → `app/db/repository.py` 写入 → `app/metrics/calculator.py` 计算指标 → `app/rules/engine.py` 评估告警规则 → `app/agents/graph.py` LangGraph Agent 分析 → 飞书同步

### 核心模块

- **`app/main.py`** — FastAPI 应用入口，`create_app()` 工厂函数。所有 API 路由集中定义
- **`app/db/models.py`** — SQLAlchemy ORM 模型。核心表：`SkuMaster`（SKU主数据）、`SalesDaily`/`AdsDaily`/`InventoryDaily`/`ProfitDaily`/`ReturnReviewDaily`（日维度数据）、`AlertTask`（告警）、`DailyReport`（日报）
- **`app/db/session.py`** — 数据库连接工厂。开发用 SQLite，自动 `ensure_sqlite_dev_schema()` 补列（无需 migration）
- **`app/db/repository.py`** — 数据访问层，upsert 模式写入

### AI Agent 系统

- **`app/agents/graph.py`** — LangGraph StateGraph 构建运营分析 Agent。按告警类型路由到 sales/ads/inventory 三个专用 Agent
- **`app/agents/chat_graph.py`** — 聊天 Agent，支持多轮对话和工具调用（查询 SKU、销售、广告、库存、利润、退货数据）。SSE 流式响应
- **`app/agents/llm.py`** — LLM 客户端抽象层。`build_llm_client()` 根据环境变量创建 DeepSeek 或 Static（回退）客户端。未配置 `DEEPSEEK_API_KEY` 时自动回退到 `StaticLLMClient`（返回固定文案），确保系统在无 AI 配置时仍可运行
- **`app/agents/tools.py`** — 聊天 Agent 的工具函数实现
- **`app/agents/parser.py`** — Agent 响应 JSON 解析，带 fallback 逻辑

### 分析模块

- **`app/analysis/battlefield.py`** — 战场地图（竞品分析）
- **`app/analysis/diagnosis.py`** — 运营天眼（产品健康度诊断）
- **`app/analysis/product_research.py`** — AI 选品分析，接入 DeepSeek
- **`app/analysis/ad_optimizer.py`** — 广告优化策略生成器（预算、ACoS、关键词 → 广告方案）
- **`app/analysis/listing_optimizer.py`** — Listing 优化规则生成器（产品描述 + 关键词 → Listing 内容 + 评分）
- **`app/analysis/supply_chain.py`** — 供应链分析本地估算模型（产品、采购量、市场、物流 → 成本方案）

### 其他模块

- **`app/rules/engine.py`** — 规则引擎，纯函数 `evaluate_alert_rules(metrics)` → 告警列表
- **`app/metrics/calculator.py`** — 指标计算，`calculate_daily_metrics()` 聚合所有数据源
- **`app/automation/scheduler.py`** — 定时任务调度器
- **`app/integrations/feishu/`** — 飞书多维表格同步
- **`app/integrations/eccang/`** — 易仓 ERP API 集成
- **`app/importers/tabular.py`** — CSV/Excel 通用解析器

### Chrome 插件数据流

Chrome 插件 → `/api/chrome/submit` 提取商品数据（ASIN、标题、价格、评分、评论数、图片） → 写入 `SkuMaster` 表 → `/api/chrome/analyze` 调用 DeepSeek 分析选品

### 前端

`app/static/` 下三个文件：`index.html`、`app.js`、`styles.css`。Vanilla JS 单页应用，通过 FastAPI 的 `StaticFiles` 挂载在 `/static`。

## 数据库

- **开发**：SQLite（`amazon_agent.db`），`ensure_sqlite_dev_schema()` 自动补列，无需运行 alembic
- **生产**：PostgreSQL，需要 `alembic upgrade head` 执行迁移
- 所有日维度表有 `(sku, date)` 唯一约束，使用 upsert 模式

## API 端点分组

- `/imports/*` — 数据导入（SKU、销售、广告、库存、利润、退货）
- `/jobs/daily-run` — 手动触发每日分析
- `/metrics/daily` / `/alerts` / `/reports/daily` — 查询接口
- `/chat` — AI 聊天（SSE 流式）
- `/api/battlefield/*` / `/api/diagnosis/*` / `/api/selection/*` — 分析工具
- `/api/ad-optimizer/*` / `/api/listing-optimizer/*` / `/api/supply-chain/*` — 新增分析工具
- `/api/automation/*` — 自动化任务管理
- `/api/chrome/*` — Chrome 插件数据接收
- `/api/settings/*` — 系统设置

## 测试

测试文件在 `tests/` 目录，使用 pytest。测试覆盖：API 端点、指标计算、规则引擎、Agent 解析器、导入器、飞书集成等。

## 部署

- **Render**：`render.yaml` 配置，免费套餐，SQLite
- **Vercel**：`vercel.json` 仅部署前端静态文件
- **腾讯云**：`deploy.sh` 脚本

## 常见问题排查

### 端口冲突

启动时如果报端口占用错误，先检查是否有旧进程占用：
```bash
# Windows
netstat -ano | findstr :8010
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8010
kill -9 <pid>
```

### API 返回 404

如果 `/docs` 可以访问但其他端点返回 404，可能是端口被旧进程占用导致新代码未生效，先排查端口冲突。
