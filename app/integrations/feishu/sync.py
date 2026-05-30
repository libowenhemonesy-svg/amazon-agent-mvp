from __future__ import annotations

from typing import Any

from app.integrations.feishu.client import FeishuClient


def sync_daily_outputs(
    *,
    client: FeishuClient,
    sku_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    report: dict[str, Any],
) -> dict[str, int]:
    counts = {
        "sku": _sync_skus(client, sku_rows),
        "metrics": _sync_metrics(client, metrics),
        "alerts": _sync_alerts(client, alerts),
        "reports": _sync_report(client, report),
    }
    return counts


def _sync_skus(client: FeishuClient, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        client.upsert_record(
            table_name="sku",
            unique_key=str(row.get("sku", "")),
            fields={
                "SKU": row.get("sku", ""),
                "ASIN": row.get("asin") or "",
                "店铺": row.get("store") or "",
                "站点": row.get("marketplace") or "",
                "分类": row.get("product_category") or "",
                "生命周期": row.get("lifecycle") or "",
                "负责人": row.get("owner") or "",
                "负责 Agent": row.get("responsible_agent") or "",
                "目标 ACOS": row.get("target_acos", 0),
                "目标毛利率": row.get("target_gross_margin", 0),
                "安全库存天数": row.get("safety_stock_days", 0),
                "是否启用监控": bool(row.get("enabled", True)),
            },
        )
    return len(rows)


def _sync_metrics(client: FeishuClient, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        run_date = _date_text(row.get("date"))
        sku = str(row.get("sku", ""))
        client.upsert_record(
            table_name="metrics",
            unique_key=f"{run_date}:{sku}",
            fields={
                "日期": run_date,
                "SKU": sku,
                "销量": row.get("units_sold", 0),
                "销售额": row.get("sales_amount", 0),
                "ACOS": row.get("acos", 0),
                "CVR": row.get("cvr", 0),
                "库存天数": row.get("inventory_days", 0),
                "毛利率": row.get("gross_margin", 0),
                "退货率": row.get("return_rate", 0),
            },
        )
    return len(rows)


def _sync_alerts(client: FeishuClient, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        run_date = _date_text(row.get("date"))
        sku = str(row.get("sku", ""))
        alert_type = str(row.get("alert_type", ""))
        agent_result = row.get("agent_result") or {}
        client.upsert_record(
            table_name="alerts",
            unique_key=f"{run_date}:{sku}:{alert_type}",
            fields={
                "日期": run_date,
                "SKU": sku,
                "异常类型": alert_type,
                "严重程度": row.get("severity", ""),
                "Agent 建议": agent_result.get("summary", row.get("reason", "")),
                "建议动作": "\n".join(agent_result.get("recommended_actions", [])[:3]),
                "状态": row.get("status", "pending"),
            },
        )
    return len(rows)


def _sync_report(client: FeishuClient, report: dict[str, Any]) -> int:
    if not report:
        return 0
    run_date = _date_text(report.get("date"))
    client.upsert_record(
        table_name="reports",
        unique_key=run_date,
        fields={
            "日期": run_date,
            "报告类型": "日报",
            "核心结论": report.get("summary", ""),
            "风险数量": report.get("risk_count", 0),
            "待处理事项": report.get("pending_count", 0),
        },
    )
    return 1


def _date_text(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")
