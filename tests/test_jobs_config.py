from datetime import date

from app.routes.jobs import init_jobs_config


def test_daily_run_uses_configured_feishu_flag(monkeypatch):
    captured = {}

    def fake_run_daily_analysis(*, run_date, session, feishu_enabled):
        captured["run_date"] = run_date
        captured["session"] = session
        captured["feishu_enabled"] = feishu_enabled
        return {"ok": True}

    monkeypatch.setattr("app.routes.jobs.run_daily_analysis", fake_run_daily_analysis)
    init_jobs_config(feishu_enabled=False)

    from app.routes.jobs import daily_run

    result = daily_run(date(2026, 1, 1), session=object())

    assert result == {"ok": True}
    assert captured["feishu_enabled"] is False
