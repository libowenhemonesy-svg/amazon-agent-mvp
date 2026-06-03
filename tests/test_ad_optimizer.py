from app.analysis.ad_optimizer import AdOptimizer


def test_ad_optimizer_generates_complete_campaign_strategy():
    optimizer = AdOptimizer()

    result = optimizer.optimize(
        product_keyword="portable blender",
        daily_budget=50,
        target_acos=0.2,
        marketplace="US",
        category="Kitchen",
        ad_type="Sponsored Products",
    )

    assert result["metrics"]["daily_budget"] == 50
    assert result["metrics"]["target_acos"] == 20
    assert result["metrics"]["estimated_roas"] > 0
    assert result["budget_allocation"]["total_daily_budget"] == 50
    assert {item["channel"] for item in result["budget_allocation"]["items"]} == {
        "Sponsored Products",
        "Sponsored Brands",
        "Sponsored Display",
    }
    assert result["keyword_bids"]
    assert {"keyword", "match_type", "suggested_bid", "competition"} <= result["keyword_bids"][0].keys()
    assert result["negative_keywords"]
    assert result["dayparting_strategy"]
    assert result["launch_plan"]
    assert result["risk_controls"]
    assert "portable blender" in result["report"]


def test_ad_optimizer_rejects_invalid_budget():
    optimizer = AdOptimizer()

    try:
        optimizer.optimize(
            product_keyword="portable blender",
            daily_budget=0,
            target_acos=0.2,
            marketplace="US",
            category="Kitchen",
            ad_type="Sponsored Products",
        )
    except ValueError as exc:
        assert "预算" in str(exc)
    else:
        raise AssertionError("expected invalid budget to raise ValueError")
