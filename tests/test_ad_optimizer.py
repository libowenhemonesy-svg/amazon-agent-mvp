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

    # 核心指标
    assert result["metrics"]["daily_spend"] == 50
    assert result["metrics"]["target_acos"] == 20
    assert result["metrics"]["roas"] > 0

    # 预算分配
    assert result["budget_allocation"]["total_daily_budget"] == 50
    assert {item["channel"] for item in result["budget_allocation"]["items"]} == {
        "Sponsored Products",
        "Sponsored Brands",
        "Sponsored Display",
    }

    # 关键词竞价
    assert result["keyword_bids"]
    assert {"keyword", "match_type", "suggested_bid", "competition"} <= result["keyword_bids"][0].keys()

    # 否定词
    assert result["negative_keywords"]

    # 分时策略
    assert result["dayparting_strategy"]
    assert len(result["dayparting_strategy"]) == 24

    # 广告结构建议（新增）
    assert result["campaign_structure"]
    assert result["campaign_structure"]["campaigns"]

    # ASIN 定向建议（新增）
    assert result["asin_targeting"]
    assert result["asin_targeting"]["strategies"]

    # 投放节奏
    assert result["launch_plan"]

    # 风险控制
    assert result["risk_controls"]

    # 趋势分析（新增，无数据时为 insufficient_data）
    assert result["trend_analysis"]

    # 报告
    assert "portable blender" in result["report"]

    # 数据来源标记（新增）
    assert result["data_source"] == "estimated"  # 无数据库时为估算模式


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


def test_ad_optimizer_rejects_invalid_acos():
    optimizer = AdOptimizer()

    try:
        optimizer.optimize(
            product_keyword="portable blender",
            daily_budget=50,
            target_acos=1.5,  # 超出 0-1 范围
            marketplace="US",
            category="Kitchen",
            ad_type="Sponsored Products",
        )
    except ValueError as exc:
        assert "ACoS" in str(exc)
    else:
        raise AssertionError("expected invalid ACoS to raise ValueError")


def test_ad_optimizer_keyword_bids_have_adjust_factor():
    optimizer = AdOptimizer()

    result = optimizer.optimize(
        product_keyword="wireless headphones",
        daily_budget=100,
        target_acos=0.25,
    )

    for bid in result["keyword_bids"]:
        assert "adjust_factor" in bid
        assert "action" in bid
        assert bid["action"] in ("降价", "加价", "维持")


def test_ad_optimizer_campaign_structure_phases():
    optimizer = AdOptimizer()

    # 新品期（无 SKU 信息时默认）
    result = optimizer.optimize(
        product_keyword="test product",
        daily_budget=30,
        target_acos=0.3,
    )
    # 无 SKU 信息时 lifecycle 默认为 stable，走成熟期
    assert result["campaign_structure"]["phase"] in ("新品期", "成熟期")
    assert len(result["campaign_structure"]["campaigns"]) >= 3
