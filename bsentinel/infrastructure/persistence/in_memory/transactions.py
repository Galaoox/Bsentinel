"""Optimistic copy-on-write transaction; never restore shared global state.

Publication has no await: compare and publish are indivisible on the app event loop.
A concurrent catalog writer aborts the bulk with an infrastructure error rather
than overwriting it. This adapter is process-local and not thread-safe.
"""
from copy import deepcopy
from types import TracebackType
from typing import Self

from .store import InMemoryStore


class InMemoryCatalogTransaction:
    fields = ("books", "relations", "history", "stores")

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.working = InMemoryStore()

    async def __aenter__(self) -> Self:
        self.baseline = {field: deepcopy(getattr(self.store, field)) for field in self.fields}
        for field, value in self.baseline.items():
            setattr(self.working, field, deepcopy(value))
        return self

    async def flush(self) -> None:
        pass

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            return
        if any(getattr(self.store, field) != value for field, value in self.baseline.items()):
            raise RuntimeError("Concurrent in-memory catalog change; retry the bulk request")
        for field in ("books", "relations", "history"):
            setattr(self.store, field, getattr(self.working, field))
