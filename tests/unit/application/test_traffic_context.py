import asyncio
from datetime import UTC, datetime


async def test_batch_context_isolates_three_workers_and_restores_parent():
    from bsentinel.application.services.scraping_batch import ScrapingBatch
    from bsentinel.application.services.traffic_context import attribution
    from bsentinel.domain.models import BookStoreRelation

    rows = [BookStoreRelation(next_check_at=datetime.now(UTC), scrape_group=0) for _ in range(3)]
    seen = []

    async def page(cutoff, limit, after):
        return rows if after is None else []

    async def process(row, cutoff):
        before = dict(attribution.get())
        await asyncio.sleep(0)
        assert attribution.get() == before
        seen.append(before)
        assert before["relation_id"] == str(row.id)
        assert before["scope"] == "periodic"
        return "successful"

    summary = await ScrapingBatch(page, process, clock=lambda: datetime(2026, 10, 8, 13, tzinfo=UTC)).run()
    assert len({v["batch_id"] for v in seen}) == 1
    assert len({v["operation_id"] for v in seen}) == 3
    assert summary.batch_id == seen[0]["batch_id"]
    assert attribution.get() == {}


async def test_root_manual_and_catalog_attribution_restores_context(monkeypatch):
    import importlib
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from starlette.requests import Request
    from starlette.responses import Response

    from bsentinel.application.services.traffic_context import attribution
    from bsentinel.domain.models import BookStoreRelation

    root = importlib.import_module("bsentinel.infrastructure.api.root_app")
    seen = []

    async def next_handler(request):
        seen.append(dict(attribution.get()))
        return Response()

    await root.add_request_id(Request({"type": "http", "headers": []}), next_handler)
    assert seen[0]["scope"] == "catalog"
    assert attribution.get() == {}

    async def get_relation(relation_id):
        return None

    @asynccontextmanager
    async def repos():
        yield SimpleNamespace(relations=SimpleNamespace(get=get_relation))

    class Processor:
        def __init__(self, *args):
            pass

        async def process(self, relation, cutoff, **kwargs):
            seen.append(dict(attribution.get()))

    monkeypatch.setattr(root, "RelationProcessor", Processor)
    monkeypatch.setattr(root, "_scraping_repositories", repos)
    relation = BookStoreRelation()
    await root._refresh_relation(relation)
    assert seen[1]["scope"] == "manual"
    assert seen[1]["relation_id"] == str(relation.id)
    assert attribution.get() == {}
