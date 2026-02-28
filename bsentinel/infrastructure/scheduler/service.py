"""Scheduler local con APScheduler."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bsentinel.application.services import BookService

logger = logging.getLogger(__name__)


class LocalScheduler:
    def __init__(self, service: BookService) -> None:
        self.service = service
        self.scheduler = AsyncIOScheduler()

    def start(self, interval_hours: int = 6) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(self._run_scraping, "interval", hours=interval_hours, id="scrape_all")
        self.scheduler.start()
        logger.info("APScheduler local iniciado", extra={"interval_hours": interval_hours})

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def trigger_now(self) -> None:
        asyncio.create_task(self._run_scraping())

    async def _run_scraping(self) -> None:
        updated = await self.service.scrape_all_active()
        logger.info("Scraping batch ejecutado", extra={"updated_relations": updated})
