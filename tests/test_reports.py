from app.reports.director import build_director_report


def test_build_director_report_summarizes_risks_by_severity_and_module():
    alerts = [
        {
            "sku": "SKU-001",
            "alert_type": "inventory_below_safety",
            "severity": "high",
            "status": "pending",
            "agent_result": {
                "summary": "库存低于安全天数",
                "recommended_actions": ["确认补货计划", "暂停广告", "检查在途库存"],
            },
        },
        {
            "sku": "SKU-002",
            "alert_type": "acos_high",
            "severity": "medium",
            "status": "pending",
            "agent_result": {
                "summary": "ACOS 偏高",
                "recommended_actions": ["检查搜索词"],
            },
        },
    ]

    report = build_director_report("2026-01-08", alerts)

    assert report["risk_count"] == 2
    assert report["severity_counts"] == {"high": 1, "medium": 1, "low": 0}
    assert report["module_counts"]["inventory"] == 1
    assert report["module_counts"]["ads"] == 1
    assert report["top_risks"][0]["sku"] == "SKU-001"
    assert report["top_risks"][0]["recommended_actions"] == ["确认补货计划", "暂停广告"]
    assert "高风险 1 个" in report["summary"]


def test_build_director_report_truncates_long_agent_summaries():
    alerts = [
        {
            "sku": "SKU-001",
            "alert_type": "inventory_below_safety",
            "severity": "high",
            "status": "pending",
            "agent_result": {"summary": "长篇报告" * 100, "recommended_actions": []},
        }
    ]

    report = build_director_report("2026-01-08", alerts)

    assert len(report["top_risks"][0]["summary"]) <= 80
