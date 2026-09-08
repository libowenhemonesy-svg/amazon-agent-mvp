import os

from app.env import load_env_file


def test_load_env_file_sets_missing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# local config",
                "FEISHU_APP_TOKEN=app_token",
                "FEISHU_TABLE_SKU=tbl_sku",
                "EMPTY_VALUE=",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("FEISHU_APP_TOKEN", raising=False)
    monkeypatch.delenv("FEISHU_TABLE_SKU", raising=False)
    monkeypatch.delenv("EMPTY_VALUE", raising=False)

    load_env_file(env_file)

    assert os.environ["FEISHU_APP_TOKEN"] == "app_token"
    assert os.environ["FEISHU_TABLE_SKU"] == "tbl_sku"
    assert os.environ["EMPTY_VALUE"] == ""


def test_load_env_file_keeps_existing_environment_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("FEISHU_APP_TOKEN=file_value", encoding="utf-8")
    monkeypatch.setenv("FEISHU_APP_TOKEN", "system_value")

    load_env_file(env_file)

    assert os.environ["FEISHU_APP_TOKEN"] == "system_value"


def test_load_env_file_replaces_empty_environment_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("BAILIAN_API_KEY=file_value", encoding="utf-8")
    monkeypatch.setenv("BAILIAN_API_KEY", "")

    load_env_file(env_file)

    assert os.environ["BAILIAN_API_KEY"] == "file_value"


def test_load_env_file_can_override_existing_environment_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=file_value", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "system_value")

    load_env_file(env_file, override=True)

    assert os.environ["DEEPSEEK_API_KEY"] == "file_value"
