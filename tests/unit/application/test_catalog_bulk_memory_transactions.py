import importlib

import pytest

from bsentinel.domain.models import Book
from bsentinel.infrastructure.persistence.in_memory import InMemoryStore


def transaction(store):
    module = importlib.import_module('bsentinel.infrastructure.persistence.in_memory.transactions')
    return module.InMemoryCatalogTransaction(store)


async def test_memory_publishes_only_on_success():
    store = InMemoryStore()
    tx = transaction(store)
    book = Book(title='Working', authors=['Author'], isbn='1')
    async with tx:
        tx.working.books[book.id] = book
        await tx.flush()
        assert not store.books
    assert store.books[book.id] == book


async def test_memory_failure_does_not_erase_concurrent_write():
    store = InMemoryStore()
    tx = transaction(store)
    other = Book(title='Concurrent', authors=[], isbn='2')
    with pytest.raises(RuntimeError, match='failure'):
        async with tx:
            book = Book(title='Working', authors=[], isbn='1')
            tx.working.books[book.id] = book
            store.books[other.id] = other
            raise RuntimeError('failure')
    assert store.books == {other.id: other}


async def test_memory_detects_concurrent_catalog_changes_without_overwrite():
    store = InMemoryStore()
    tx = transaction(store)
    other = Book(title='Concurrent', authors=[], isbn='2')
    with pytest.raises(RuntimeError, match='Concurrent'):
        async with tx:
            book = Book(title='Working', authors=[], isbn='1')
            tx.working.books[book.id] = book
            store.books[other.id] = other
    assert store.books == {other.id: other}
