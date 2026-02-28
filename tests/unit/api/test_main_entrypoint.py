from bsentinel.infrastructure.api.__main__ import main


def test_main_calls_uvicorn_with_expected_args(monkeypatch):
    called = {}

    def fake_run(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr("bsentinel.infrastructure.api.__main__.uvicorn.run", fake_run)
    main()

    assert called["args"][0] == "bsentinel.infrastructure.api:root_app"
    assert called["kwargs"]["host"] == "0.0.0.0"
    assert isinstance(called["kwargs"]["port"], int)
