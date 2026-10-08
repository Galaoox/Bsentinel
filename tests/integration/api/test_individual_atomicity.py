import importlib

import pytest

from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.in_memory.transactions import InMemoryCatalogTransaction

URL = 'https://www.buscalibre.com.co/book-isbn-9780132350884'


@pytest.mark.parametrize('backend', ['sql', 'in_memory'])
@pytest.mark.parametrize('failure', ['scraping', 'invalid_isbn'])
def test_individual_failure_rolls_back_and_retry_succeeds(client, monkeypatch, backend, failure):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    monkeypatch.setattr(module.settings, 'persistence_backend', backend)
    auth = client.post('/api/v1/auth/login', data={'username': 'admin', 'password': 'changeme'})
    headers = {'Authorization': 'Bearer ' + auth.json()['access_token']}
    original = module.scraper_client.scrape_book
    async def fail(*args):
        raise ScrapingError('isolated failure')
    if failure == 'scraping':
        monkeypatch.setattr(module.scraper_client, 'scrape_book', fail)
    response = client.post('/api/v1/catalog/books', json={
        'url': URL if failure == 'scraping' else URL.replace('9780132350884', '9780132350885')}, headers=headers)
    assert response.status_code == 400
    assert response.json()['error']['code'] == ('SCRAPING_ERROR' if failure == 'scraping' else 'VALIDATION_ERROR')
    assert 'index' not in response.json()['error']['details']
    assert 'url' not in response.json()['error']['details']
    assert client.get('/api/v1/catalog/books', headers=headers).json()['meta']['total'] == 0
    if backend == 'in_memory':
        assert not module.in_memory_store.relations and not module.in_memory_store.history
    monkeypatch.setattr(module.scraper_client, 'scrape_book', original)
    retry = client.post('/api/v1/catalog/books', json={'url': URL}, headers=headers)
    assert retry.status_code == 201, retry.text
    assert 'url' not in retry.json() and 'index' not in retry.json()


@pytest.mark.parametrize('method', ['flush', '__aexit__'])
def test_memory_individual_flush_or_publication_failure_is_atomic(client, monkeypatch, method):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    monkeypatch.setattr(module.settings, 'persistence_backend', 'in_memory')
    auth = client.post('/api/v1/auth/login', data={'username': 'admin', 'password': 'changeme'})
    headers = {'Authorization': 'Bearer ' + auth.json()['access_token']}
    original = getattr(InMemoryCatalogTransaction, method)
    async def fail(*args):
        raise RuntimeError('isolated publication failure')
    monkeypatch.setattr(InMemoryCatalogTransaction, method, fail)
    monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    response = client.post('/api/v1/catalog/books', json={'url': URL}, headers=headers)
    assert response.status_code == 500
    assert not module.in_memory_store.books and not module.in_memory_store.relations and not module.in_memory_store.history
    monkeypatch.setattr(InMemoryCatalogTransaction, method, original)
    assert client.post('/api/v1/catalog/books', json={'url': URL}, headers=headers).status_code == 201


def test_api_sqlite_unicode_search_uses_production_engine_configuration(client):
    import sqlite3
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    auth = client.post('/api/v1/auth/login', data={'username': 'admin', 'password': 'changeme'})
    headers = {'Authorization': 'Bearer ' + auth.json()['access_token']}
    created = client.post('/api/v1/catalog/books', json={'url': URL}, headers=headers)
    assert created.status_code == 201
    key = created.json()['book_id']
    path = module.settings.database_url.removeprefix('sqlite+aiosqlite:///')
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE books SET title=? WHERE id=?', ('ÁRBOL', key))
        connection.execute('UPDATE book_authors SET author=? WHERE book_id=?', ('ÁRBOL', key))
    for filter_key in ['q', 'author']:
        response = client.get('/api/v1/catalog/books', params={filter_key: 'árbol'}, headers=headers)
        assert response.status_code == 200
        assert response.json()['meta']['total'] == 1
        assert response.json()['items'][0]['book_id'] == key


def test_unicode_wrong_credentials_return_401(client):
    for username, password in [('á', 'changeme'), ('admin', 'contraseña')]:
        response = client.post('/api/v1/auth/login', data={'username': username, 'password': password})
        assert response.status_code == 401
        assert response.json()['error']['code'] == 'AUTH_INVALID_CREDENTIALS'
