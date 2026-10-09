import pytest

ENDPOINT = "/api/v1/catalog/books/bulk"
URL = "https://www.buscalibre.com.co/book-isbn-9780134494166"


def headers(client):
    response = client.post('/api/v1/auth/login', data={
        'username': 'admin', 'password': 'changeme'
    })
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_bulk_accepts_aliases_and_returns_canonical_sites(client):
    auth = headers(client)
    urls = [
        "https://buscalibre.com.co/book-isbn-9780134494166?ref=affiliate%2Fid",
        "https://panamericana.com.co/book-isbn-9780132350884/p",
    ]

    response = client.post(ENDPOINT, json={"urls": urls}, headers=auth)

    assert response.status_code == 201, response.text
    body = response.json()
    assert [item["url"] for item in body["items"]] == urls
    assert [item["site"] for item in body["items"]] == [
        "www.buscalibre.com.co",
        "www.panamericana.com.co",
    ]


def test_alias_duplicate_returns_409_and_rolls_back(client):
    auth = headers(client)
    urls = [URL, URL.replace("www.buscalibre.com.co", "buscalibre.com.co")]

    response = client.post(ENDPOINT, json={"urls": urls}, headers=auth)

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"index": 1, "url": urls[1]}
    assert client.get("/api/v1/catalog/books", headers=auth).json()["meta"]["total"] == 0


def test_bulk_creates_ordered_relations_shared_isbn_and_history(client):
    auth = headers(client)
    urls = [URL, URL.replace("www.buscalibre.com.co", "www.panamericana.com.co")]
    response = client.post(ENDPOINT, json={"urls": urls}, headers=auth)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meta"] == {"total": 2}
    assert [item["url"] for item in body["items"]] == urls
    assert [item["index"] for item in body["items"]] == [0, 1]
    assert body["items"][0]["book_id"] == body["items"][1]["book_id"]
    book_id = body["items"][0]["book_id"]
    detail = client.get("/api/v1/catalog/books/" + book_id, headers=auth).json()
    assert len(detail["stores"]) == 2
    assert all(store["price"] == 42.5 for store in detail["stores"])
    history = client.get("/api/v1/pricing/books/" + book_id + "/history", headers=auth).json()
    assert history["meta"]["total"] == 2


@pytest.mark.parametrize("bad_url,code,status", [
    ("not-a-url", "VALIDATION_ERROR", 400),
    ("https://unsupported.example/book", "UNSUPPORTED_STORE", 400),
    (URL + "-alternate", "ENTITY_ALREADY_EXISTS", 409),
])
def test_item_error_is_indexed_and_rolls_back(client, bad_url, code, status):
    auth = headers(client)
    response = client.post(ENDPOINT, json={"urls": [URL, bad_url]}, headers=auth)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["details"] == {"index": 1, "url": bad_url}
    assert client.get('/api/v1/catalog/books', headers=auth).json()['meta']['total'] == 0
    assert_sql_catalog_counts((0, 0, 0))
    assert response.json()['request_id'] == response.headers['X-Request-ID']


@pytest.mark.parametrize("urls", [[], [URL] * 21, [1], [URL, URL], ["x" * 2049]])
def test_structural_validation_prevents_scraping(client, monkeypatch, urls):
    import importlib
    root_app = importlib.import_module('bsentinel.infrastructure.api.root_app')
    async def forbidden(*args):
        pytest.fail("Scraper must not be invoked")
    monkeypatch.setattr(root_app.scraper_client, 'extract_book_details', forbidden)
    response = client.post(ENDPOINT, json={'urls': urls}, headers=headers(client))
    assert response.status_code == 422


def test_scraping_error_sanitized_and_rolls_back(client, monkeypatch):
    import importlib

    from bsentinel.exceptions import ScrapingError
    root_app = importlib.import_module('bsentinel.infrastructure.api.root_app')
    original = root_app.scraper_client.scrape_book
    async def fail_second(store, url):
        if 'second' in url:
            raise ScrapingError('proxy http://user:password@proxy.example:8000 failed',
                                diagnostics={'proxy': 'http://user:password@proxy.example:8000'})
        return await original(store, url)
    monkeypatch.setattr(root_app.scraper_client, 'scrape_book', fail_second)
    second = URL.replace('9780134494166', '9780132350884') + '-second'
    response = client.post(ENDPOINT, json={'urls': [URL, second]}, headers=headers(client))
    assert response.status_code == 400
    assert response.json()['error']['details']['index'] == 1
    assert response.json()['error']['code'] == 'SCRAPING_ERROR'
    assert 'password' not in response.text
    assert client.get('/api/v1/catalog/books', headers=headers(client)).json()['meta']['total'] == 0


@pytest.mark.parametrize('fails', [False, True])
def test_memory_backend_bulk_is_atomic(client, monkeypatch, fails):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    monkeypatch.setattr(module.settings, 'persistence_backend', 'in_memory')
    urls = [URL, 'invalid' if fails else URL.replace('9780134494166', '9780132350884')]
    auth = headers(client)
    response = client.post(ENDPOINT, json={'urls': urls}, headers=auth)
    assert response.status_code == (400 if fails else 201)
    assert len(module.in_memory_store.books) == (0 if fails else 2)
    assert len(module.in_memory_store.relations) == (0 if fails else 2)
    assert len(module.in_memory_store.history) == (0 if fails else 2)


@pytest.mark.parametrize('method', ['commit', 'flush'])
@pytest.mark.parametrize('bulk', [False, True])
def test_persistence_failure_never_returns_created(client, monkeypatch, method, bulk):
    from sqlalchemy.ext.asyncio import AsyncSession
    auth = headers(client)
    original = getattr(AsyncSession, method)
    async def fail_bulk(self, *args, **kwargs):
        if self.info.get('bulk_owns_transaction'):
            raise RuntimeError('private infrastructure details')
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(AsyncSession, method, fail_bulk)
    monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    response = client.post(ENDPOINT if bulk else '/api/v1/catalog/books',
                           json={'urls': [URL]} if bulk else {'url': URL}, headers=auth)
    assert response.status_code == 500
    assert 'private' not in response.text
    assert response.json()['request_id'] == response.headers['X-Request-ID']
    assert client.get('/api/v1/catalog/books', headers=auth).json()['meta']['total'] == 0
    assert_sql_catalog_counts((0, 0, 0))
    monkeypatch.setattr(AsyncSession, method, original)
    retry = client.post(ENDPOINT if bulk else '/api/v1/catalog/books',
                        json={'urls': [URL]} if bulk else {'url': URL}, headers=auth)
    assert retry.status_code == 201, retry.text


def test_bulk_twenty_items_are_persisted(client):
    auth = headers(client)
    prefixes = [str(978013449416 + i) for i in range(20)]
    isbns = [prefix + str((-sum(int(char) * (1 if index % 2 == 0 else 3)
                               for index, char in enumerate(prefix))) % 10) for prefix in prefixes]
    urls = [URL.replace('9780134494166', isbn) for isbn in isbns]
    response = client.post(ENDPOINT, json={'urls': urls}, headers=auth)
    assert response.status_code == 201
    payload = response.json()
    assert payload['meta'] == {'total': 20}
    assert [i['index'] for i in payload['items']] == list(range(20))
    assert [i['url'] for i in payload['items']] == urls
    assert client.get('/api/v1/catalog/books', headers=auth).json()['meta']['total'] == 20
    for item in payload['items']:
        history = client.get('/api/v1/pricing/books/' + item['book_id'] + '/history', headers=auth)
        assert history.json()['meta']['total'] == 1


@pytest.mark.parametrize('auth', [{}, {'Authorization': 'Bearer invalid'}])
def test_bulk_requires_valid_jwt(client, auth):
    response = client.post(ENDPOINT, json={'urls': [URL]}, headers=auth)
    assert response.status_code == 401


def test_existing_deleted_book_reused_without_enrichment_or_restore(client, monkeypatch):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    auth = headers(client)
    created = client.post('/api/v1/catalog/books', json={'url': URL}, headers=auth).json()
    book_id = created['book_id']
    assert client.delete('/api/v1/catalog/books/' + book_id, headers=auth).status_code == 204
    async def forbidden(isbn):
        pytest.fail('Existing book must not be enriched again')
    monkeypatch.setattr(module.metadata_client, 'enrich_by_isbn', forbidden)
    response = client.post(ENDPOINT, json={'urls': [URL.replace('www.buscalibre.com.co', 'www.panamericana.com.co')]}, headers=auth)
    assert response.status_code == 201
    assert response.json()['items'][0]['book_id'] == book_id
    assert client.get('/api/v1/catalog/books/' + book_id, headers=auth).json()['is_deleted'] is True
    assert client.post('/api/v1/catalog/books/' + book_id + '/restore', headers=auth).status_code == 200


def assert_sql_catalog_counts(expected):
    import importlib
    import sqlite3
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    path = module.settings.database_url.removeprefix('sqlite+aiosqlite:///')
    assert 'bsentinel-test-' in path
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        counts = tuple(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                       for table in ['books', 'book_store_relations', 'price_history'])
    assert counts == expected


@pytest.mark.parametrize('invalid_shape', ['duplicates', 'too_long'])
def test_structural_errors_do_not_expose_url_credentials(client, monkeypatch, invalid_shape):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    private_url = 'https://private-user:private-password@www.buscalibre.com.co/book'
    urls = [private_url, private_url] if invalid_shape == 'duplicates' else [private_url + 'x' * 2049]
    async def forbidden(*args):
        pytest.fail('Structural errors must not invoke scraping')
    monkeypatch.setattr(module.scraper_client, 'extract_book_details', forbidden)
    response = client.post(ENDPOINT, json={'urls': urls}, headers=headers(client))
    assert response.status_code == 422
    assert 'private-user' not in response.text
    assert 'private-password' not in response.text
    errors = response.json()['error']['details']['errors']
    assert errors
    assert all('input' not in error for error in errors)
    assert errors[0]['loc'] == (['body', 'urls'] if invalid_shape == 'duplicates' else ['body', 'urls', 0])
    assert response.json()['request_id'] == response.headers['X-Request-ID']
    assert_sql_catalog_counts((0, 0, 0))


@pytest.mark.parametrize('bulk', [False, True])
def test_malformed_bracket_url_returns_validation_error(client, monkeypatch, bulk):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    bad_url = 'https://[invalid/book'
    monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    original = module.scraper_client.extract_book_details
    async def reject_bad_url(store, url):
        assert url != bad_url, 'Malformed URL must not invoke scraping'
        return await original(store, url)
    monkeypatch.setattr(module.scraper_client, 'extract_book_details', reject_bad_url)
    auth = headers(client)
    response = client.post(
        ENDPOINT if bulk else '/api/v1/catalog/books',
        json={'urls': [URL, bad_url]} if bulk else {'url': bad_url},
        headers=auth,
    )
    assert response.status_code == 400, response.text
    error = response.json()['error']
    assert error['code'] == 'VALIDATION_ERROR'
    assert error['message'] == 'Invalid URL'
    assert error['details'] == ({'index': 1, 'url': bad_url} if bulk else {})
    assert response.json()['request_id'] == response.headers['X-Request-ID']
    assert_sql_catalog_counts((0, 0, 0))


def test_validation_error_context_credentials_are_sanitized():
    import asyncio
    import importlib
    import json

    from fastapi import Request
    from fastapi.exceptions import RequestValidationError

    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    private_url = 'https://ctx-user:ctx-password@proxy.example:8000/book'
    request = Request({'type': 'http'})
    request.state.request_id = 'validation-context-regression'
    error = RequestValidationError([{
        'type': 'value_error', 'loc': ('body', 'urls'),
        'msg': 'Value error, ' + private_url, 'input': {'urls': [private_url]},
        'ctx': {'error': ValueError(private_url), 'nested': {'urls': [private_url]}},
    }])
    response = asyncio.run(module.request_validation_exception_handler(request, error))
    body = bytes(response.body).decode()
    assert response.status_code == 422
    assert 'ctx-user' not in body
    assert 'ctx-password' not in body
    detail = json.loads(body)['error']['details']['errors'][0]
    assert 'input' not in detail
    assert detail['loc'] == ['body', 'urls']
    assert detail['ctx']['error'] == 'https://***:***@proxy.example:8000/book'
    assert response.headers['X-Request-ID'] == request.state.request_id


@pytest.mark.parametrize('bulk', [False, True])
def test_scraper_value_error_remains_internal_error(client, monkeypatch, bulk):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    async def fail(*args):
        raise ValueError('private scraper infrastructure failure')
    monkeypatch.setattr(module.scraper_client, 'extract_book_details', fail)
    monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    response = client.post(
        ENDPOINT if bulk else '/api/v1/catalog/books',
        json={'urls': [URL]} if bulk else {'url': URL}, headers=headers(client),
    )
    assert response.status_code == 500
    assert response.json()['error']['code'] == 'INTERNAL_SERVER_ERROR'
    assert 'private scraper' not in response.text
    assert_sql_catalog_counts((0, 0, 0))


def test_error_item_url_credentials_are_redacted(client):
    bad = 'https://user:private-value@www.buscalibre.com.co/book-isbn-1'
    response = client.post(ENDPOINT, json={'urls': [URL, bad]}, headers=headers(client))
    assert response.status_code == 400
    assert response.json()['error']['details']['index'] == 1
    assert 'private-value' not in response.text
    assert_sql_catalog_counts((0, 0, 0))


@pytest.mark.parametrize('failure', ['inactive_store', 'missing_isbn', 'metadata'])
def test_second_item_failure_removes_books_relations_and_histories(client, monkeypatch, failure):
    import importlib
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    auth = headers(client)
    if failure == 'inactive_store':
        second = URL.replace('www.buscalibre.com.co', 'www.panamericana.com.co')
        import sqlite3
        path = module.settings.database_url.removeprefix('sqlite+aiosqlite:///')
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE stores SET is_active=0 WHERE domain='www.panamericana.com.co'")
    elif failure == 'missing_isbn':
        second = 'https://www.buscalibre.com.co/book-no-isbn'
    else:
        second = URL.replace('9780134494166', '9780132350884')
        original = module.metadata_client.enrich_by_isbn
        async def fail_second(isbn):
            if isbn == '9780132350884':
                raise RuntimeError('private metadata infrastructure detail')
            return await original(isbn)
        monkeypatch.setattr(module.metadata_client, 'enrich_by_isbn', fail_second)
        monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    response = client.post(ENDPOINT, json={'urls': [URL, second]}, headers=auth)
    assert response.status_code == (500 if failure == 'metadata' else 400)
    assert 'private metadata' not in response.text
    assert_sql_catalog_counts((0, 0, 0))
