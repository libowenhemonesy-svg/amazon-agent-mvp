from app.routes.demo import init_demo_config


def test_load_sample_demo_uses_configured_feishu_flag(monkeypatch):
    captured = {}

    monkeypatch.setattr("app.routes.demo.upsert_sku_rows", lambda session, rows: 0)
    monkeypatch.setattr("app.routes.demo.upsert_daily_rows", lambda session, model, rows: 0)
    monkeypatch.setattr("app.routes.demo._parse_sample_file", lambda *args, **kwargs: [])

    def fake_run_daily_analysis(*, run_date, session, feishu_enabled):
        captured["feishu_enabled"] = feishu_enabled
        return {"ok": True}

    monkeypatch.setattr("app.routes.demo.run_daily_analysis", fake_run_daily_analysis)
    init_demo_config(feishu_enabled=False)

    from app.routes.demo import load_sample_demo

    result = load_sample_demo(session=object())

    assert result["ok"] is True
    assert captured["feishu_enabled"] is False
