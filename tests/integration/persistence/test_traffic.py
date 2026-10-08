from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_traffic_persists_independent_events_and_aggregates_sql(schedule_db):
    from bsentinel.domain.traffic import TrafficEvent
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, _ = schedule_db
    now = datetime.now(UTC)
    events = [
        TrafficEvent(
            domain="shop.invalid",
            outcome="failed",
            download_bytes=10,
            upload_bytes=0,
            request_bytes=100,
            header_bytes=20,
            redirects=0,
            completeness="known",
            scope="periodic",
            batch_id="batch",
            operation_id="operation",
        ),
        TrafficEvent(
            domain="shop.invalid",
            outcome="successful",
            download_bytes=50,
            upload_bytes=0,
            request_bytes=100,
            header_bytes=20,
            redirects=0,
            completeness="known",
            scope="periodic",
            batch_id="batch",
            operation_id="operation",
        ),
        TrafficEvent(domain="shop.invalid", outcome="cancelled", scope="manual"),
    ]
    async with factory() as session:
        repo = SQLTrafficRepository(session)
        for event in events:
            await repo.add(event)
        await session.commit()
    async with factory() as session:
        result = await SQLTrafficRepository(session).report(
            now - timedelta(hours=1), now + timedelta(hours=1), relation_count=3
        )
    assert result["observed"]["attempts"] == 3
    assert result["observed"]["known_bytes"] == 300
    assert result["observed"]["sent_request_bytes"] == 200
    assert result["observed"]["received_http_bytes"] == 100
    assert result["observed"]["failed_attempts"] == 2
    assert result["process_health"]["missing_writes_since_start"] >= 0
    assert result["observed"]["unknown_attempts"] == 1
    assert result["projection"]["sample_operations"] == 1
    assert result["projection"]["bytes_24h"] == 1800
    assert result["projection"]["bytes_30d"] == 54000
    assert result["projection"]["relation_count"] == 3
    assert result["projection"]["relation_count_source"] == "requested"
    assert len(result["daily"]) == 1
    assert len(result["monthly"]) == 1
    assert result["batches"][0]["batch_id"] == "batch"
    assert "shop.invalid" not in str(result)


@pytest.mark.asyncio
async def test_no_sample_is_insufficient_not_zero(schedule_db):
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, _ = schedule_db
    now = datetime.now(UTC)
    async with factory() as session:
        result = await SQLTrafficRepository(session).report(now - timedelta(days=1), now)
    assert result["projection"]["status"] == "insufficient_sample"
    assert result["projection"]["bytes_24h"] is None
    assert result["projection"]["relation_count_source"] == "current_dataset"


@pytest.mark.asyncio
async def test_root_sink_commits_even_when_price_transaction_rolls_back(schedule_db, monkeypatch):
    import importlib
    from types import SimpleNamespace

    from bsentinel.domain.traffic import TrafficEvent

    root_module = importlib.import_module("bsentinel.infrastructure.api.root_app")
    from sqlalchemy import select

    from bsentinel.infrastructure.persistence.sqlalchemy.traffic_model import TrafficEventModel
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, _ = schedule_db

    async def isolated_scope():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(root_module, "session_scope", isolated_scope)
    monkeypatch.setattr(root_module, "settings", SimpleNamespace(persistence_backend="sqlalchemy"))
    event = TrafficEvent(
        domain="shop.invalid", outcome="http_error", http_status=403, download_bytes=520
    )
    async with factory() as price_session:
        await root_module._persist_traffic(event)
        await price_session.rollback()
    async with factory() as session:
        stored = (
            await session.execute(select(TrafficEventModel).where(TrafficEventModel.id == event.id))
        ).scalar_one()
        assert stored.http_status == 403
        assert stored.download_bytes == 520
        now = datetime.now(UTC)
        report = await SQLTrafficRepository(session).report(
            now - timedelta(days=1), now + timedelta(hours=1)
        )
        assert report["observed"]["http_403_attempts"] == 1
        assert report["observed"]["successful_attempts"] == 0
        assert report["projection"]["status"] == "insufficient_sample"


@pytest.mark.asyncio
async def test_postgres_daily_buckets_are_utc_not_session_timezone(schedule_db):
    from sqlalchemy import text

    from bsentinel.domain.traffic import TrafficEvent
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, _ = schedule_db
    now = datetime(2026, 10, 8, 0, 30, tzinfo=UTC)
    async with factory() as session:
        if session.bind.dialect.name != "postgresql":
            pytest.skip("PostgreSQL timezone contract")
        await session.execute(text("SET LOCAL TIME ZONE 'America/Bogota'"))
        repo = SQLTrafficRepository(session)
        await repo.add(TrafficEvent(domain="shop.invalid", outcome="failed", observed_at=now))
        result = await repo.report(now - timedelta(hours=1), now + timedelta(hours=1))
        assert str(result["daily"][0]["date"]) == "2026-10-08"


@pytest.mark.asyncio
async def test_batch_limit_does_not_hide_overflow_with_unattributed_events(schedule_db):
    from bsentinel.domain.traffic import TrafficEvent
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, _ = schedule_db
    now = datetime.now(UTC)
    async with factory() as session:
        repo = SQLTrafficRepository(session)
        await repo.add(TrafficEvent(domain="shop.invalid", outcome="failed"))
        for i in range(102):
            await repo.add(
                TrafficEvent(domain="shop.invalid", outcome="failed", batch_id=f"{i:036d}")
            )
        result = await repo.report(now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(result["batches"]) == 100
        assert result["batches_truncated"] is True


@pytest.mark.asyncio
async def test_current_dataset_count_comes_from_active_sql_relations(schedule_db):
    from sqlalchemy import update

    from bsentinel.infrastructure.persistence.sqlalchemy.models import (
        BookStoreRelationModel,
        StoreModel,
    )
    from bsentinel.infrastructure.persistence.traffic import SQLTrafficRepository

    factory, ids = schedule_db
    now = datetime.now(UTC)
    async with factory() as session:
        session.add(
            BookStoreRelationModel(
                book_id=ids[0],
                store_id=ids[1],
                product_url="https://shop.invalid/book",
                status="activo",
                next_check_at=now,
                scrape_group=0,
                created_at=now,
            )
        )
        await session.flush()
        repo = SQLTrafficRepository(session)
        report = await repo.report(now - timedelta(hours=1), now + timedelta(hours=1))
        assert report["projection"]["relation_count"] == 1
        assert report["projection"]["relation_count_source"] == "current_dataset"
        await session.execute(
            update(StoreModel).where(StoreModel.id == ids[1]).values(is_active=False)
        )
        report = await repo.report(now - timedelta(hours=1), now + timedelta(hours=1))
        assert report["projection"]["relation_count"] == 0
