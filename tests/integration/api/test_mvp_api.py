from uuid import UUID


def login_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "changeme"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_endpoint_and_request_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    UUID(response.headers["X-Request-ID"])


def test_login_refresh_and_logout_flow(client):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "changeme"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["token_type"] == "bearer"
    assert login_payload["expires_in"] == 3600

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_payload = refresh_response.json()
    assert refreshed_payload["refresh_token"] != login_payload["refresh_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed_payload["refresh_token"]},
    )
    assert logout_response.status_code == 204

    revoked_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refreshed_payload["refresh_token"]},
    )
    assert revoked_refresh.status_code == 401
    assert revoked_refresh.json()["error"]["code"] == "AUTH_REFRESH_REVOKED"


def test_protected_v1_endpoints_reject_anonymous_requests(client):
    response = client.get("/api/v1/system/info")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


def test_create_book_and_list_flow(client):
    payload = {"url": "https://www.buscalibre.com.co/libro-el-principito-isbn-9780156012195"}
    headers = login_headers(client)
    create_response = client.post("/api/v1/catalog/books", json=payload, headers=headers)
    assert create_response.status_code == 201
    body = create_response.json()
    UUID(body["book_id"])
    assert body["site"] == "www.buscalibre.com.co"
    assert body["isbn"] == "9780156012195"

    list_response = client.get("/api/v1/catalog/books", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["items"]
    assert len(listed) == 1
    assert listed[0]["status"] == "activo"
    assert listed[0]["title"] == "Libro El Principito 9780156012195"


def test_create_duplicate_book_relation_returns_409(client):
    payload = {"url": "https://www.buscalibre.com.co/libro-pragmatic-programmer-isbn-9780135957059"}
    headers = login_headers(client)
    assert client.post("/api/v1/catalog/books", json=payload, headers=headers).status_code == 201
    duplicate = client.post("/api/v1/catalog/books", json=payload, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ENTITY_ALREADY_EXISTS"


def test_create_book_without_isbn_returns_400(client):
    payload = {"url": "https://www.buscalibre.com.co/libro-sin-isbn"}
    response = client.post("/api/v1/catalog/books", json=payload, headers=login_headers(client))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_book_with_unsupported_store_returns_400(client):
    payload = {"url": "https://example.com/book/123"}
    response = client.post("/api/v1/catalog/books", json=payload, headers=login_headers(client))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_STORE"


def test_delete_and_restore_book(client):
    headers = login_headers(client)
    create = client.post(
        "/api/v1/catalog/books",
        json={"url": "https://www.buscalibre.com.co/libro-clean-code-isbn-9780132350884"},
        headers=headers,
    )
    book_id = create.json()["book_id"]

    delete_response = client.delete(f"/api/v1/catalog/books/{book_id}", headers=headers)
    assert delete_response.status_code == 204

    listed = client.get("/api/v1/catalog/books", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 0

    restore = client.post(f"/api/v1/catalog/books/{book_id}/restore", headers=headers)
    assert restore.status_code == 200
    assert restore.json()["is_deleted"] is False


def test_history_and_price_comparison_endpoints(client):
    headers = login_headers(client)
    create = client.post(
        "/api/v1/catalog/books",
        json={"url": "https://www.buscalibre.com.co/libro-domain-driven-design-isbn-9780321125217"},
        headers=headers,
    )
    book_id = create.json()["book_id"]

    history = client.get(f"/api/v1/pricing/books/{book_id}/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["meta"]["total"] >= 1

    comparison = client.get(f"/api/v1/pricing/books/{book_id}/comparison", headers=headers)
    assert comparison.status_code == 200
    assert comparison.json()["best_offer"] is not None


def test_archive_job_flow(client):
    headers = login_headers(client)
    create = client.post(
        "/api/v1/catalog/books",
        json={"url": "https://www.buscalibre.com.co/libro-refactoring-isbn-9780134757599"},
        headers=headers,
    )
    assert create.status_code == 201

    create_job = client.post(
        "/api/v1/retention/jobs/archive",
        json={"older_than_days": 1, "min_active_records_per_book": 1},
        headers=headers,
    )
    assert create_job.status_code == 202
    job_id = create_job.json()["id"]

    job_status = client.get(f"/api/v1/retention/jobs/archive/{job_id}", headers=headers)
    assert job_status.status_code == 200
    assert job_status.json()["status"] in {"completed", "running", "queued"}
