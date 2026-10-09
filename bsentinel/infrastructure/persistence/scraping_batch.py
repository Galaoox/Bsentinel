"""Short repository contexts around snapshots and independent atomic results."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, AsyncContextManager
from uuid import UUID

from bsentinel.application.ports import ScraperPort
from bsentinel.domain.models import BookStoreRelation, PriceHistoryRecord, Store
from bsentinel.domain.scraping_schedule import current_slot, initial_check, next_check
from bsentinel.exceptions import ScrapingError, UnsupportedStoreError
from bsentinel.infrastructure.scraping.store_guard import (
    check_periodic_admission,
    periodic_admission,
)

logger = logging.getLogger(__name__)


class RelationLocks:
    """Reference counted: no permanent lock per catalog URL."""

    def __init__(self) -> None:
        self._entries: dict[UUID, tuple[asyncio.Lock, int]] = {}

    @asynccontextmanager
    async def hold(self, relation_id: UUID) -> AsyncIterator[None]:
        lock, users = self._entries.get(relation_id, (asyncio.Lock(), 0))
        self._entries[relation_id] = (lock, users + 1)
        try:
            async with lock:
                yield
        finally:
            remaining = self._entries[relation_id][1] - 1
            if remaining:
                self._entries[relation_id] = (lock, remaining)
            else:
                del self._entries[relation_id]


relation_locks = RelationLocks()


class RelationProcessor:
    def __init__(
        self,
        context: Callable[[], AsyncContextManager[Any]],
        scraper: ScraperPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        locks: RelationLocks = relation_locks,
    ) -> None:
        self.context = context
        self.scraper = scraper
        self.clock = clock
        self.locks = locks

    async def list_page(
        self, cutoff: datetime, limit: int, after: tuple[datetime, UUID] | None
    ) -> list[BookStoreRelation]:
        async with self.context() as repos:
            return deepcopy(await repos.relations.list_due(cutoff, limit, after))

    def _omitted(self, candidate: BookStoreRelation, reason: str) -> None:
        logger.info(
            "Scraping relation omitted",
            extra={"relation_id": str(candidate.id), "omission_reason": reason},
        )
        return None

    async def _snapshot(
        self,
        repos,
        candidate: BookStoreRelation,
        cutoff: datetime,
        force: bool = False,
        lock: bool = False,
    ) -> tuple[BookStoreRelation, Store] | None:
        getter = (
            getattr(repos.relations, "get_for_update", repos.relations.get)
            if lock
            else repos.relations.get
        )
        current = await getter(candidate.id)
        if current is None:
            return self._omitted(candidate, "missing")
        if current.product_url != candidate.product_url:
            return self._omitted(candidate, "url_changed")
        if current.scrape_generation != candidate.scrape_generation:
            return self._omitted(candidate, "invalidated")
        if current.next_check_at != candidate.next_check_at:
            return self._omitted(candidate, "rescheduled")
        if current.next_check_at is None or (not force and current.next_check_at > cutoff):
            return self._omitted(candidate, "not_due")
        book = await repos.books.get(current.book_id)
        store = await repos.stores.get(current.store_id)
        if not book or book.is_deleted or not store or store.is_deleted or not store.is_active:
            return self._omitted(candidate, "disabled")
        return deepcopy(current), deepcopy(store)

    async def process(
        self, candidate: BookStoreRelation, cutoff: datetime, *, force: bool = False
    ) -> str:
        if not force and not isinstance(cutoff, datetime):
            raise ValueError("schedule requires timezone-aware timestamps")
        candidate = deepcopy(candidate)
        async with self.locks.hold(candidate.id):
            # The batch cutoff identifies the authorized cohort, never a queued row's start.
            slot = None if force else current_slot(candidate.scrape_group, cutoff)
            async with self.context() as repos:
                snapshot = await self._snapshot(repos, candidate, cutoff, force, lock=not force)
                if not force and current_slot(candidate.scrape_group, self.clock()) != slot:
                    slot = None
                if snapshot is not None and not force and slot is not None:
                    reserved, store = snapshot
                    # Consume the authorized window durably BEFORE HTTP. A crash,
                    # cancellation or result transaction failure cannot replay it.
                    reserved.next_check_at = next_check(reserved.scrape_group, slot, self.clock())
                    reserved.scrape_generation += 1
                    await repos.relations.save(reserved)
                    candidate = deepcopy(reserved)
                    snapshot = reserved, store
            if snapshot is None:
                return "omitted"
            relation, store = snapshot
            skipped = not force and slot is None
            failed = skipped
            fetch_error = None
            result = None
            try:
                if not skipped:
                    token = periodic_admission.set(
                        None if force else lambda: current_slot(relation.scrape_group, self.clock()) == slot
                    )
                    try:
                        check_periodic_admission()
                        result = await self.scraper.scrape_book(store, relation.product_url)
                    finally:
                        periodic_admission.reset(token)
            except (ScrapingError, UnsupportedStoreError) as exc:
                failed = True
                fetch_error = exc
                logger.warning(
                    "Scraping attempt failed",
                    extra={"relation_id": str(relation.id), "error_type": type(exc).__name__,
                           "scraping_reason": getattr(exc, "reason", None)},
                )
            finished = self.clock()
            async with self.context() as repos:
                snapshot = await self._snapshot(repos, candidate, cutoff, force or slot is not None, lock=True)
                if snapshot is None:
                    return "omitted"
                current, _ = snapshot
                if force:
                    # A manual operation invalidates concurrent snapshots, not a future window.
                    current.scrape_generation += 1
                    if current.next_check_at <= finished:
                        current.next_check_at = initial_check(current.scrape_group, finished, current.last_checked)
                elif skipped:
                    # Expired work cannot consume a later window it never entered.
                    current.next_check_at = initial_check(current.scrape_group, cutoff, current.last_checked)
                else:
                    reschedule_at = cutoff if getattr(fetch_error, "reason", None) == "schedule_skipped" else finished
                    current.next_check_at = next_check(current.scrape_group, slot, reschedule_at)
                if not failed:
                    assert result is not None
                    current.current_price = result.price
                    current.status = result.status
                    current.last_checked = result.checked_at
                    await repos.history.add(
                        PriceHistoryRecord(
                            book_id=current.book_id,
                            relation_id=current.id,
                            store_id=current.store_id,
                            price=result.price,
                            state=result.status,
                            checked_at=result.checked_at,
                        )
                    )
                await repos.relations.save(current)
            # Context exit commits; SQL failures abort the batch without replaying its reservation.
            if force and fetch_error is not None:
                raise fetch_error
            reason = getattr(fetch_error, "reason", None)
            if skipped or reason == "schedule_skipped":
                return "skipped"
            if reason == "store_paused":
                return "paused"
            if reason in {"captcha_blocked", "challenge_blocked"}:
                return "captcha" if reason == "captcha_blocked" else "blocked"
            return "failed" if failed else "successful"
