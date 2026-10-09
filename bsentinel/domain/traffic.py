"""Transport observations; absent counters are unknown, never zero."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from bsentinel.domain.scraping_schedule import DAILY_REVIEW_COUNT


@dataclass(frozen=True)
class TrafficEvent:
    domain: str
    outcome: str
    http_status: int | None = None
    download_bytes: int | None = None
    upload_bytes: int | None = None
    request_bytes: int | None = None
    header_bytes: int | None = None
    redirects: int | None = None
    completeness: str = "unknown"
    scope: str = "unattributed"
    batch_id: str | None = None
    relation_id: str | None = None
    operation_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def project_traffic(
    *,
    sample_operations: int,
    mean_bytes: float | None,
    relation_count: int,
    relation_count_source: str,
) -> dict:
    mean = float(mean_bytes) if sample_operations and mean_bytes is not None else None
    return {
        "status": "estimated" if mean is not None else "insufficient_sample",
        "sample_operations": sample_operations,
        "mean_bytes_per_operation": mean,
        "relation_count": relation_count,
        "relation_count_source": relation_count_source,
        "scheduled_reviews_per_relation_day": DAILY_REVIEW_COUNT,
        "bytes_24h": mean * relation_count * DAILY_REVIEW_COUNT if mean is not None else None,
        "bytes_30d": mean * relation_count * DAILY_REVIEW_COUNT * 30 if mean is not None else None,
        "assumptions": [
            "two scheduled reviews per active relation daily at 08/17 America/Bogota",
            "manual and catalog requests add traffic beyond nominal scheduled reviews",
            "three groups spaced 20 minutes",
            "complete periodic samples only; retries included",
            "unchanged catalog, response sizes and retry distribution",
            "24 hours and 30 days; not Decodo billing or monetary cost",
        ],
    }
