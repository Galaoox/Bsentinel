"""In-memory persistence adapters."""

from .archive_jobs import InMemoryArchiveJobRepository
from .auth import InMemoryRefreshTokenRepository
from .books import InMemoryBookRepository
from .history import InMemoryHistoryRepository
from .relations import InMemoryRelationRepository
from .store import InMemoryStore
from .stores import InMemoryStoreRepository

__all__ = [
    "InMemoryArchiveJobRepository",
    "InMemoryBookRepository",
    "InMemoryHistoryRepository",
    "InMemoryRefreshTokenRepository",
    "InMemoryRelationRepository",
    "InMemoryStore",
    "InMemoryStoreRepository",
]
