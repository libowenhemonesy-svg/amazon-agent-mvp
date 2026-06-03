from app.analysis.supply_chain import SupplyChainAnalyzer


def test_supply_chain_analyzer_generates_cost_logistics_and_restock_plan():
    analyzer = SupplyChainAnalyzer()

    result = analyzer.analyze(
        product="portable blender",
        purchase_quantity=1200,
        marketplace="US",
        logistics_method="FBA sea freight",
        budget=12000,
        category="Kitchen",
    )

    assert result["summary"]["product"] == "portable blender"
    assert result["summary"]["purchase_quantity"] == 1200
    assert result["cost_analysis"]["total_cost"] > 0
    assert result["cost_analysis"]["cost_per_unit"] > 0
    assert result["supplier_evaluation"]
    assert result["logistics_plan"]["method"] == "FBA sea freight"
    assert result["inventory_plan"]["first_stock_units"] > 0
    assert result["inventory_plan"]["reorder_point_units"] > 0
    assert result["cash_flow"]["budget_usage_rate"] > 0
    assert result["risk_controls"]
    assert "portable blender" in result["report"]


def test_supply_chain_analyzer_rejects_invalid_quantity():
    analyzer = SupplyChainAnalyzer()

    try:
        analyzer.analyze(
            product="portable blender",
            purchase_quantity=0,
            marketplace="US",
            logistics_method="FBA sea freight",
            budget=12000,
            category="Kitchen",
        )
    except ValueError as exc:
        assert "采购量" in str(exc)
    else:
        raise AssertionError("expected invalid quantity to raise ValueError")
