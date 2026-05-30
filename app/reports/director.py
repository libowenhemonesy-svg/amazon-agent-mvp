from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_director_report(run_date: str, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    module_counts = {"sales": 0, "ads": 0, "inventory": 0, "profit": 0, "quality": 0, "other": 0}
    for alert in alerts:
        severity = alert.get("severity", "medium")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        module = _module_for_alert(alert.get("alert_type", ""))
        module_counts[module] = module_counts.get(module, 0) + 1

    sorted_alerts = sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_ORDER.get(alert.get("severity", "medium"), 1),
            alert.get("sku", ""),
        ),
    )
    top_risks = [
        {
            "sku": alert.get("sku"),
            "alert_type": alert.get("alert_type"),
            "severity": alert.get("severity"),
            "summary": _short_text(
                alert.get("agent_result", {}).get("summary", alert.get("reason", "")),
                limit=80,
            ),
            "recommended_actions": _list(
                alert.get("agent_result", {}).get("recommended_actions", []),
                limit=2,
            ),
        }
        for alert in sorted_alerts[:10]
    ]
    pending_count = sum(1 for alert in alerts if alert.get("status") == "pending")
    summary = (
        f"{run_date} 经营简报：共发现 {len(alerts)} 个异常，"
        f"高风险 {severity_counts.get('high', 0)} 个，中风险 {severity_counts.get('medium', 0)} 个，"
        f"待处理 {pending_count} 个。"
    )
    return {
        "date": run_date,
        "summary": summary,
        "risk_count": len(alerts),
        "pending_count": pending_count,
        "severity_counts": severity_counts,
        "module_counts": module_counts,
        "top_risks": top_risks,
    }


def _module_for_alert(alert_type: str) -> str:
    if alert_type.startswith("sales"):
        return "sales"
    if alert_type in {"acos_high", "clicks_without_orders"}:
        return "ads"
    if alert_type.startswith("inventory"):
        return "inventory"
    if alert_type.startswith("profit"):
        return "profit"
    if alert_type.startswith("quality"):
        return "quality"
    return "other"


def _short_text(value: Any, *, limit: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:limit]


def _list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:80] for item in value[:limit]]
