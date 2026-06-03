from app.analysis.product_research import ProductResearchAnalyzer


def test_product_research_prioritizes_keyword_matched_competitors():
    analyzer = ProductResearchAnalyzer()
    competitors = [
        {
            "asin": "B0FAN001",
            "title": "Portable Fan Rechargeable Mini Handheld Fan",
            "price": 29.99,
            "rating": 4.6,
            "review_count": 380,
            "url": "https://amazon.example/B0FAN001",
            "marketplace": "US",
        },
        {
            "asin": "B0LAMP01",
            "title": "Desk Lamp with USB Charging Port",
            "price": 19.99,
            "rating": 4.2,
            "review_count": 900,
            "url": "https://amazon.example/B0LAMP01",
            "marketplace": "US",
        },
    ]

    result = analyzer.analyze(
        keyword="portable fan",
        marketplace="US",
        category="all",
        competitors=competitors,
    )

    assert result["keyword"] == "portable fan"
    assert result["market_overview"]["sample_size"] == 1
    assert result["market_overview"]["avg_price"] == 29.99
    assert result["competitors"][0]["asin"] == "B0FAN001"
    assert result["keywords"]
    assert result["pricing_advice"]["target_price_min"] > 0
    assert result["decision"]["status"] in {"go", "cautious", "no_go"}
    assert "能不能做" in result["report"]
    assert result["generated_by_ai"] is False


def test_product_research_falls_back_when_no_keyword_match():
    analyzer = ProductResearchAnalyzer()
    competitors = [
        {
            "asin": "B0LAMP01",
            "title": "Desk Lamp with USB Charging Port",
            "price": 19.99,
            "rating": 4.2,
            "review_count": 900,
            "url": "",
            "marketplace": "US",
        }
    ]

    result = analyzer.analyze(
        keyword="portable fan",
        marketplace="US",
        category="all",
        competitors=competitors,
    )

    assert result["market_overview"]["sample_limited"] is True
    assert result["market_overview"]["sample_note"]
    assert result["competitors"][0]["asin"] == "B0LAMP01"
    assert result["decision"]["reasons"]


def test_product_research_marks_missing_competitor_fields():
    analyzer = ProductResearchAnalyzer()

    result = analyzer.analyze(
        keyword="kitchen rack",
        marketplace="US",
        category="all",
        competitors=[
            {
                "asin": "B0RACK01",
                "title": "Kitchen Rack Storage Shelf",
                "price": 0,
                "rating": 4.6,
                "review_count": 0,
                "main_image": "https://example.test/rack.jpg",
                "url": "",
                "marketplace": "US",
            }
        ],
    )

    competitor = result["competitors"][0]
    assert competitor["has_price"] is False
    assert competitor["has_review_count"] is False
    assert competitor["main_image"] == "https://example.test/rack.jpg"
    assert competitor["data_quality_notes"] == ["价格未采集", "评论数未采集"]
