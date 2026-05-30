# Amazon Agent MVP

轻量版亚马逊运营 Agent 后端，支持 CSV/Excel 导入、每日 SKU 指标计算、规则预警、LangGraph Agent 建议和飞书多维表同步边界。

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy / Alembic
- PostgreSQL for deployment, SQLite for local smoke tests
- Pandas / openpyxl
- LangGraph

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[test]
Copy-Item .env.example .env
```

For PostgreSQL, set `DATABASE_URL` and run:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Without `DATABASE_URL`, `app.main:app` uses a local SQLite file for development.

## DeepSeek

The Agent layer uses a static local response by default. To use DeepSeek, set these variables before starting the API:

```powershell
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="your_deepseek_api_key"
$env:DEEPSEEK_MODEL="deepseek-chat"
```

Then start the server:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Optional settings:

- `DEEPSEEK_BASE_URL`, defaults to `https://api.deepseek.com`
- `DEEPSEEK_TIMEOUT_SECONDS`, defaults to `30`

The integration calls DeepSeek's OpenAI-compatible chat completions endpoint and falls back to the static client only when `LLM_PROVIDER` is not `deepseek` or no API key is configured.

Agent prompts require DeepSeek to return compact JSON rather than a long Markdown report:

```json
{
  "summary": "库存低于补货周期，存在断货风险",
  "root_causes": ["可售库存为0", "无在途库存"],
  "diagnostic_checks": ["确认补货单", "检查FBA状态"],
  "recommended_actions": ["立即确认补货计划", "暂停广告"],
  "priority": 1,
  "immediate_action_required": true
}
```

If the model returns malformed JSON or long prose, the Agent layer uses a short fallback task-card response so reports and Feishu tasks stay readable.

## API

- `POST /imports/sku`
- `POST /imports/sales`
- `POST /imports/ads`
- `POST /imports/inventory`
- `POST /imports/profit`
- `POST /imports/returns`
- `POST /demo/load-sample`
- `POST /jobs/daily-run?run_date=YYYY-MM-DD`
- `GET /metrics/daily?date=YYYY-MM-DD`
- `GET /alerts?date=YYYY-MM-DD`
- `PATCH /alerts/{id}`
- `GET /reports/daily?date=YYYY-MM-DD`

## Dashboard

Start the API and open the local dashboard:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Then visit:

```text
http://127.0.0.1:8000/
```

The dashboard supports:

- Loading bundled sample data and running analysis with one click
- Uploading SKU, sales, ads, inventory, profit, and returns/reviews CSV/XLSX files
- Running daily analysis for the selected date
- Viewing risk counts, risk bars, module distribution, and the daily director report
- Viewing alert tasks and concise Agent recommendations
- Updating alert status: `pending`, `processing`, `done`, `reviewed`, `ignored`
- Showing Feishu sync status after each run: `disabled`, `skipped`, `synced`, or `failed`

For a quick demo with no real data, click `载入示例并分析`. It imports the files in
`sample_data/`, runs the `2026-01-07` analysis, and refreshes the dashboard. The bundled demo has six SKU scenarios: sales decline, advertising waste, inventory risk, profit risk, quality risk, and one normal SKU.

## Feishu Sync

When these environment variables are set, `daily-run` syncs four Bitable tables:

- `FEISHU_APP_TOKEN`
- `FEISHU_TENANT_ACCESS_TOKEN` or both `FEISHU_APP_ID` and `FEISHU_APP_SECRET`
- `FEISHU_TABLE_SKU`: SKU master data
- `FEISHU_TABLE_METRICS`: daily SKU monitoring metrics
- `FEISHU_TABLE_ALERTS`: alert tasks and Agent recommendations
- `FEISHU_TABLE_REPORTS`: archived daily reports

If `FEISHU_TENANT_ACCESS_TOKEN` is empty, the app exchanges `FEISHU_APP_ID` and
`FEISHU_APP_SECRET` for a tenant token at runtime. If any Feishu table id or auth
setting is missing, analysis still runs and returns `feishu_sync.status = skipped`.

## Current Analysis Method

The MVP focuses on the main operations loop:

1. Calculate SKU-level metrics across SKU master, sales, ads, inventory, profit, and return/review modules.
2. Apply configurable alert rules with SKU lifecycle, SKU thresholds, profit targets, and quality thresholds.
3. Attach `rule_context` to every alert so Agent output has explicit observed values, baselines, thresholds, and units.
4. Route alerts through LangGraph to sales, ads, or inventory Agent nodes.
5. Return structured Agent output:
   - `summary`
   - `possible_causes`
   - `diagnostic_checks`
   - `recommended_actions`
   - `priority`
   - `immediate_action_required`
6. Build a director-style daily report with severity counts, module counts, pending count, and top risks.

Low-volume SKU sales alerts are suppressed by default when the 7-day average is below 5 units, which reduces noisy false positives for new or low-velocity products.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```
