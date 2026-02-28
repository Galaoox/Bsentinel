import pytest

from bsentinel.application.services import RetentionService
from bsentinel.exceptions import ValidationError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryArchiveJobRepository,
    InMemoryStore,
)


def test_retention_service_rejects_invalid_parameters():
    storage = InMemoryStore()
    service = RetentionService(jobs=InMemoryArchiveJobRepository(storage))

    with pytest.raises(ValidationError):
        service.create_archive_job(older_than_days=0, min_active_records_per_book=1)

    with pytest.raises(ValidationError):
        service.create_archive_job(older_than_days=1, min_active_records_per_book=0)
