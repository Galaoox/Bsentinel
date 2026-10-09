"""Store circuit admission, shared by every configured scraper entry point.

The runtime takes the global permit BEFORE this guard. Publication happens before
release. Only expired circuits serialize a single half-open probe. SQL persistence
owns short independent sessions; catalog rollback cannot erase a block.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from bsentinel.exceptions import ScrapingError

logger = logging.getLogger(__name__)
fetch_admission: ContextVar[object] = ContextVar('store_fetch_admission', default=None)
periodic_admission: ContextVar[object] = ContextVar('periodic_admission', default=None)


def check_periodic_admission():
    check = periodic_admission.get()
    if check is not None and not check():
        raise ScrapingError('Periodic window expired', reason='schedule_skipped')


@dataclass(frozen=True)
class BlockState:
    blocked_until: datetime
    reason: str


class MemoryBlockPersistence:
    def __init__(self):
        self.states = {}

    async def read(self, store_id):
        return self.states.get(str(store_id))

    async def extend(self, store_id, state):
        key = str(store_id)
        previous = self.states.get(key)
        if previous is None or previous.blocked_until <= state.blocked_until:
            self.states[key] = state
        return self.states[key]

    async def clear(self, store_id, observed):
        if self.states.get(str(store_id)) == observed:
            self.states.pop(str(store_id), None)


@dataclass
class Admission:
    guard: 'StoreGuard'
    store: object
    classify: object


class StoreGuard:
    def __init__(self, persistence, *, cooldown_minutes=60, clock=lambda: datetime.now(UTC)):
        self.persistence = persistence
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.clock = clock
        self.entries = {}
        # Fail-closed protection when the independent persistence write fails.
        self._unpublished = {}

    def _paused(self, store, state):
        return ScrapingError(
            f'Store {store.domain} is paused', reason='store_paused',
            diagnostics={'store_id': str(store.id), 'store_domain': store.domain,
                         'blocked_reason': state.reason,
                         'blocked_until': state.blocked_until.astimezone(UTC).isoformat()},
        )

    async def state(self, store):
        saved = await self.persistence.read(store.id)
        local = self._unpublished.get(str(store.id))
        if local and (saved is None or local.blocked_until > saved.blocked_until):
            return local
        return saved

    async def check(self, store):
        check_periodic_admission()
        state = await self.state(store)
        if state and state.blocked_until > self.clock():
            raise self._paused(store, state)
        return state

    @asynccontextmanager
    async def request(self, store, classify):
        key = str(store.id)
        lock, users = self.entries.get(key, (asyncio.Lock(), 0))
        self.entries[key] = (lock, users + 1)
        probe = False
        observed = None
        try:
            # Atomic admission bookkeeping; never hold the lock for normal HTTP.
            async with lock:
                observed = await self.check(store)
                if observed is not None:
                    # Other expired-circuit entrants fail fast, not queue a burst.
                    if getattr(lock, '_store_probe', False):
                        raise self._paused(store, observed)
                    lock._store_probe = True
                    probe = True
            async def publish(page):
                classification = classify(store, page)
                if classification.kind == 'blocked':
                    state = BlockState(self.clock() + self.cooldown, classification.reason)
                    self._unpublished[key] = state
                    saved = await self.persistence.extend(store.id, state)
                    self._unpublished.pop(key, None)
                    logger.warning('Store scraping paused', extra={
                        'store_id': key, 'store_domain': store.domain,
                        'scraping_reason': saved.reason,
                        'blocked_until': saved.blocked_until.astimezone(UTC).isoformat(),
                    })
                elif probe and classification.kind == 'usable':
                    await self.persistence.clear(store.id, observed)
                    if self._unpublished.get(key) == observed:
                        self._unpublished.pop(key, None)
                elif probe:
                    # A failed probe does not permit an immediate retry storm.
                    await self.persistence.extend(store.id, BlockState(self.clock() + self.cooldown, observed.reason))
                return classification
            yield publish
        except BaseException:
            if probe and observed is not None:
                await self.persistence.extend(store.id, BlockState(self.clock() + self.cooldown, observed.reason))
            raise
        finally:
            if probe:
                lock._store_probe = False
            remaining = self.entries[key][1] - 1
            if remaining:
                self.entries[key] = (lock, remaining)
            else:
                del self.entries[key]
