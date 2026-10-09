from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_metrics_endpoint_authenticated_validated_no_sample():
    from bsentinel.infrastructure.api.v1.traffic import build_traffic_router

    class Repository:
        async def report(self, start, end, **kwargs):
            return {
                "projection": {"status": "insufficient_sample", "bytes_24h": None},
                "options": kwargs,
            }

    class Auth:
        async def authenticate_access_token(self, token):
            assert token == "fixture"
            return SimpleNamespace(username="fixture", role="admin")

    app = FastAPI()
    app.include_router(build_traffic_router(lambda: Repository(), lambda: Auth()))
    client = TestClient(app)
    path = "/api/v1/metrics/traffic"
    assert client.get(path).status_code == 401
    result = client.get(path, headers={"Authorization": "Bearer fixture"})
    assert result.status_code == 200
    assert result.json()["projection"]["bytes_24h"] is None
    assert (
        client.get(
            path + "?relation_count=-1", headers={"Authorization": "Bearer fixture"}
        ).status_code
        == 422
    )
    assert (
        client.get(path + "?scope=unknown", headers={"Authorization": "Bearer fixture"}).status_code
        == 422
    )
    assert (
        client.get(
            path + "?start=2026-10-09T00:00:00Z&end=2026-10-08T00:00:00Z",
            headers={"Authorization": "Bearer fixture"},
        ).status_code
        == 422
    )
    from bsentinel.infrastructure.api.root_app import root_app

    assert path in [r.path for r in root_app.routes]
