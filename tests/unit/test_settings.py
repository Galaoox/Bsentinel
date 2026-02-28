from bsentinel._settings import Settings


def test_settings_defaults():
    cfg = Settings(_env_file=None)
    assert cfg.app_name == "bsentinel"
    assert cfg.app_version == "1.0.0"
    assert cfg.app_environment in {"local", "production"}
    assert cfg.port == 8000
    assert cfg.database_url.startswith("postgresql")


def test_settings_env_override_port(monkeypatch):
    monkeypatch.setenv("PORT", "9001")
    cfg = Settings(_env_file=None)
    assert cfg.port == 9001
