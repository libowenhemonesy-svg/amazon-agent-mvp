from app.analysis.listing_optimizer import ListingOptimizer


def test_listing_optimizer_generates_listing_and_quality_score():
    optimizer = ListingOptimizer()

    result = optimizer.optimize(
        product_description="Portable handheld fan with USB rechargeable battery, low noise motor, 3 speeds, travel size.",
        keywords=["portable fan", "handheld fan", "usb rechargeable fan", "mini fan"],
        marketplace="US",
    )

    assert result["listing"]["title"]
    assert len(result["listing"]["bullets"]) == 5
    assert result["listing"]["description"]
    assert result["listing"]["search_terms"]
    assert result["quality_score"]["overall_score"] > 0
    assert len(result["quality_score"]["dimensions"]) == 8
    assert result["keyword_coverage"]["coverage_rate"] > 0
    assert {item["keyword"] for item in result["keyword_coverage"]["items"]} == {
        "portable fan",
        "handheld fan",
        "usb rechargeable fan",
        "mini fan",
    }


def test_listing_optimizer_marks_missing_keywords():
    optimizer = ListingOptimizer()

    result = optimizer.optimize(
        product_description="Desk organizer made of bamboo.",
        keywords=["portable fan", "quiet fan"],
        marketplace="US",
    )

    statuses = {item["keyword"]: item["status"] for item in result["keyword_coverage"]["items"]}
    assert statuses["portable fan"] in {"已覆盖", "部分覆盖", "未覆盖"}
    assert statuses["quiet fan"] in {"部分覆盖", "未覆盖"}
