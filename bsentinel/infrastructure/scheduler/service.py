"""Local timer: single-process, guarded automatic/manual admission."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class LocalScheduler:
    def __init__(self, run_scraping_batch: Callable[[], Awaitable[int]]) -> None:
        self.run_scraping_batch = run_scraping_batch
        self.scheduler = AsyncIOScheduler(timezone="America/Bogota")
        self._guard = asyncio.Lock()
        self._tasks = set()
        self._closing = False

    def start(self, interval_hours: float | None = None, *, tick_minutes: int = 20) -> None:
        if self.scheduler.running:
            return
        self._closing = False
        # Arguments remain source-compatible; cadence is an absolute calendar policy.
        self.scheduler.add_job(
            self._run_scraping, 'cron', hour='8,17', minute='0,20,40',
            timezone='America/Bogota', id='scrape_all', max_instances=1,
            coalesce=True, misfire_grace_time=119,
        )
        self.scheduler.start()
        logger.info('Scraping scheduler started', extra={
            'timezone': 'America/Bogota', 'local_hours': '8,17',
            'cohort_minutes': '0,20,40', 'scrape_groups': 3, 'daily_reviews': 2,
        })

    def shutdown(self) -> None:
        self._closing = True
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        for task in tuple(self._tasks):
            task.cancel()

    async def aclose(self, timeout: float = 5) -> None:
        self.shutdown()
        if self._tasks:
            done, pending = await asyncio.wait(tuple(self._tasks), timeout=timeout)
            for task in done:
                if not task.cancelled():
                    task.exception()
            if pending:
                raise TimeoutError('Scraping workers did not stop; runtime must remain open')
        self._tasks.clear()

    def trigger_now(self) -> None:
        if self._closing or self._guard.locked() or self._tasks:
            logger.info('Scraping activation omitted: busy or closing')
            return
        task = asyncio.create_task(self._run_scraping())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_scraping(self) -> None:
        if self._closing or self._guard.locked():
            logger.info('Scraping activation omitted: busy or closing')
            return
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._guard:
                try:
                    updated = await self.run_scraping_batch()
                except Exception as exc:
                    logger.error('Scraping batch failed', extra={'error_type': type(exc).__name__})
                else:
                    logger.info('Scraping batch executed', extra={'updated_relations': updated})
        finally:
            self._tasks.discard(task)
