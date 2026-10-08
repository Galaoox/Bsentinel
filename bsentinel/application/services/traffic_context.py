"""Per-operation attribution inherited only by that task's children."""

from contextlib import contextmanager
from contextvars import ContextVar

attribution = ContextVar("traffic_attribution", default={})


@contextmanager
def traffic_context(**fields):
    token = attribution.set({**attribution.get(), **fields})
    try:
        yield
    finally:
        attribution.reset(token)
