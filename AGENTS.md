# AGENTS.md

本文件是本仓库内 AI 编码助手的项目级工作规范。除非用户给出更高优先级的明确指令，否则在本项目中工作时遵守以下规则。

## 沟通与执行原则

- 默认使用中文沟通，回复要直接、简洁、可执行。
- 新建项目或临时工程不要放在 C 盘根目录或系统目录中；本仓库工作范围为当前项目目录。
- 如果用户要求“修改某个文件、某段代码、某个功能”，只能修改用户指定范围及其必要的直接依赖；不要顺手重构无关模块。
- 修改前先阅读相关上下文，避免凭印象改代码。
- 不要覆盖用户未要求修改的本地改动；发现无关改动时忽略，发现会影响当前任务时先说明。
- 不要提交、推送、重置、删除文件，除非用户明确要求。

## 项目概览

Amazon Agent 运营台是跨境电商运营分析平台：

- 后端：Python 3.11+、FastAPI、SQLAlchemy、Alembic。
- AI：LangGraph、LangChain、DeepSeek；未配置真实 LLM 时必须拒绝生成 Agent 分析，不能回退到固定回答。
- 前端：`app/static/` 下的 Vanilla JS SPA。
- 数据库：开发环境默认 SQLite `amazon_agent.db`，生产环境 PostgreSQL。
- 外部集成：飞书、易仓 ERP、亚马逊 SP-API、卖家精灵 MCP。

## 常用命令

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
pytest
pytest tests/test_metrics.py::test_function_name
alembic upgrade head
alembic revision --autogenerate -m "描述"
```

Windows PowerShell 中优先使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

## 重要目录

- `app/main.py`：FastAPI 应用入口和路由集中定义。
- `app/agents/`：LangGraph Agent、聊天图、LLM 抽象、工具调用。
- `app/db/`：SQLAlchemy 模型、数据库会话、Repository。
- `app/importers/`：CSV/Excel 导入解析。
- `app/metrics/`：运营指标计算。
- `app/rules/`：告警规则引擎。
- `app/analysis/`：战场地图、运营天眼、选品、广告、Listing、供应链分析。
- `app/integrations/`：飞书、易仓等外部系统集成。
- `app/static/`：前端页面、脚本和样式。
- `tests/`：pytest 测试。

## 数据库与迁移

- 开发环境使用 SQLite，`app/db/session.py` 会通过 `ensure_sqlite_dev_schema()` 自动补齐部分开发字段。
- 生产环境使用 PostgreSQL，结构变更应通过 Alembic migration 管理。
- 日维度数据表通常以 `(sku, date)` 为唯一约束，写入逻辑优先保持 upsert 语义。

## AI 与 MCP 工具规则

- 卖家精灵 MCP 配置来自 `.env`：
  - `SELLERSPRITE_MCP_URL`
  - `SELLERSPRITE_API_KEY`
  - `SELLERSPRITE_MCP_TRANSPORT`
- 当调用卖家精灵 MCP 时，除了整理后的分析结论，还必须把 MCP 返回的原始数据一并发给用户，便于核对来源。
- 原始数据较长时，先给摘要，再附关键原始 JSON/表格片段；如数据量过大，应说明已截断，并保留字段名、时间、ASIN、关键词、排名、销量、价格等关键字段。
- 不要把 `.env`、API Key、Token、Cookie 等敏感信息输出给用户或写入日志。
- 禁止给项目里的 Agent 设置固定分析回答、固定 Listing、固定建议动作或假装成功的兜底文案。
- Agent 可以使用固定字段名和展示格式，例如 ASIN、标题、价格、评论数；但字段值、结论、建议和表格内容必须来自真实数据库、用户输入、采集结果、MCP 返回或真实 LLM 返回。
- 当真实 LLM、MCP、图片模型或采集数据不可用时，Agent 必须明确说明“未配置/无数据/调用失败”，不能编造示例结果或用模板内容替代真实结果。
- `StaticLLMClient` 只能作为单元测试替身显式注入，不能作为生产环境默认兜底。

## 代码风格

- Python 目标版本为 3.11，项目 ruff 行宽为 100。
- 优先沿用现有 FastAPI、SQLAlchemy、Repository、LangGraph 组织方式。
- 数据解析优先使用结构化库，例如 pandas、openpyxl、SQLAlchemy，不要用脆弱的字符串拼接替代。
- 注释只写必要的业务说明或复杂逻辑说明，避免重复解释代码本身。
- 前端保持现有 Vanilla JS/CSS 结构；除非用户明确要求，不引入新的前端框架。

## 测试与验证

- 修改后根据影响范围运行最小必要测试。
- 后端逻辑优先运行相关 pytest；广泛影响时运行完整 `pytest`。
- 语法级验证可使用：

```bash
python -m compileall app tests
```

- 如果因为环境、依赖、网络或密钥缺失无法运行测试，需要在回复中明确说明。

## API 与功能边界

- `/imports/*`：导入 SKU、销售、广告、库存、利润、退货等数据。
- `/jobs/daily-run`：手动触发每日分析。
- `/metrics/daily`、`/alerts`、`/reports/daily`：指标、告警、日报查询。
- `/chat`：AI 聊天 SSE 流式接口。
- `/api/battlefield/*`、`/api/diagnosis/*`、`/api/selection/*`：分析工具。
- `/api/ad-optimizer/*`、`/api/listing-optimizer/*`、`/api/supply-chain/*`：运营优化工具。
- `/api/automation/*`：自动化任务。
- `/api/chrome/*`：Chrome 插件数据提交和分析。
- `/api/settings/*`：系统设置。

## 安全注意事项

- 不要提交 `.env`、数据库文件、日志文件、缓存目录或本地虚拟环境。
- 处理亚马逊、飞书、易仓、卖家精灵等外部数据时，默认按业务敏感数据处理。
- 需要联网、调用外部 API、写入系统目录、安装依赖或执行潜在破坏性命令时，必须先说明原因并获得授权。
