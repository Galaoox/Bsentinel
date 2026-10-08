"""Bounded, single-process coordinator; framework/session ownership stays outside."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from bsentinel.application.services.traffic_context import traffic_context
from bsentinel.domain.models import BookStoreRelation
from bsentinel.domain.scraping_schedule import starting_group

logger = logging.getLogger(__name__)


@dataclass
class BatchSummary:
    batch_id: str = field(default_factory=lambda: str(uuid4()))
    selected: int = 0
    successful: int = 0
    failed: int = 0
    omitted: int = 0
    skipped: int = 0
    captcha: int = 0
    blocked: int = 0
    paused: int = 0
    skipped_window: bool = False
    duration_seconds: float = 0
    max_lateness_seconds: float = 0
    skipped_overlap: bool = False


class ScrapingBatch:
    def __init__(
        self,
        list_page: Callable[
            [datetime, int, tuple[datetime, UUID] | None], Awaitable[list[BookStoreRelation]]
        ],
        process: Callable[[BookStoreRelation, datetime], Awaitable[str]],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        page_size: int = 60,
    ) -> None:
        self.list_page = list_page
        self.process = process
        self.clock = clock
        self.page_size = page_size
        self._guard = asyncio.Lock()
        self.peak_queue = 0

    @property
    def running(self) -> bool:
        return self._guard.locked()

    async def run(self) -> BatchSummary:
        cutoff = self.clock()
        cohort = starting_group(cutoff)
        if cohort is None:
            return BatchSummary(skipped_window=True)
        if self.running:
            logger.info("Scraping batch omitted: already running")
            return BatchSummary(skipped_overlap=True)
        async with self._guard:
            summary = BatchSummary()
            started = monotonic()
            queue = asyncio.Queue(maxsize=6)
            self.peak_queue = 0

            async def produce():
                after = None
                while True:
                    rows = await self.list_page(cutoff, self.page_size, after)
                    if not rows:
                        break
                    # Capture cursor before workers mutate or persist these snapshots.
                    after = (rows[-1].next_check_at, rows[-1].id)
                    for row in rows:
                        if row.scrape_group != cohort:
                            continue
                        summary.selected += 1
                        summary.max_lateness_seconds = max(
                            summary.max_lateness_seconds,
                            (cutoff - row.next_check_at).total_seconds(),
                        )
                        await queue.put(row)
                        self.peak_queue = max(self.peak_queue, queue.qsize())
                for _ in range(3):
                    await queue.put(None)

            async def work():
                while True:
                    row = await queue.get()
                    try:
                        if row is None:
                            return
                        try:
                            with traffic_context(scope='periodic', batch_id=summary.batch_id,
                                                 relation_id=str(row.id), operation_id=str(uuid4())):
                                outcome = await self.process(row, cutoff)
                        except Exception as exc:
                            # Never log exception text/URLs: HTTP/SQL errors may contain credentials.
                            logger.warning(
                                "Scraping relation failed",
                                extra={
                                    "relation_id": str(row.id),
                                    "error_type": type(exc).__name__,
                                },
                            )
                            outcome = "failed"
                        setattr(summary, outcome, getattr(summary, outcome) + 1)
                    finally:
                        queue.task_done()

            # TaskGroup cancels siblings on failure/cancellation and awaits cleanup.
            async with asyncio.TaskGroup() as group:
                group.create_task(produce())
                for _ in range(3):
                    group.create_task(work())
            summary.duration_seconds = monotonic() - started
            logger.info("Scraping batch completed", extra=asdict(summary))
            return summary
