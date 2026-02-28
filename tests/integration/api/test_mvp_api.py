from uuid import UUID


def test_health_endpoint_and_request_id(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    UUID(response.headers["X-Request-ID"])


def test_create_book_and_list_flow(client):
    payload = {"url": "https://www.buscalibre.com.co/libro-el-principito-isbn-9780156012195"}
    create_response = client.post("/api/v1/catalog/books", json=payload)
    assert create_response.status_code == 201
    body = create_response.json()
    UUID(body["book_id"])
    assert body["site"] == "www.buscalibre.com.co"

    list_response = client.get("/api/v1/catalog/books")
    assert list_response.status_code == 200
    listed = list_response.json()["items"]
    assert len(listed) == 1
    assert listed[0]["status"] == "activo"


def test_create_duplicate_book_returns_409(client):
    payload = {"url": "https://www.buscalibre.com.co/libro-pragmatic-programmer"}
    assert client.post("/api/v1/catalog/books", json=payload).status_code == 201
    duplicate = client.post("/api/v1/catalog/books", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ENTITY_ALREADY_EXISTS"


def test_create_book_with_unsupported_store_returns_400(client):
    payload = {"url": "https://example.com/book/123"}
    response = client.post("/api/v1/catalog/books", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_STORE"


def test_delete_and_restore_book(client):
    create = client.post("/api/v1/catalog/books", json={"url": "https://www.buscalibre.com.co/libro-clean-code"})
    book_id = create.json()["book_id"]

    delete_response = client.delete(f"/api/v1/catalog/books/{book_id}")
    assert delete_response.status_code == 204

    listed = client.get("/api/v1/catalog/books")
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 0

    restore = client.post(f"/api/v1/catalog/books/{book_id}/restore")
    assert restore.status_code == 200
    assert restore.json()["is_deleted"] is False


def test_history_and_price_comparison_endpoints(client):
    create = client.post(
        "/api/v1/catalog/books",
        json={"url": "https://www.buscalibre.com.co/libro-domain-driven-design-isbn-9780321125217"},
    )
    book_id = create.json()["book_id"]

    history = client.get(f"/api/v1/pricing/books/{book_id}/history")
    assert history.status_code == 200
    assert history.json()["meta"]["total"] >= 1

    comparison = client.get(f"/api/v1/pricing/books/{book_id}/comparison")
    assert comparison.status_code == 200
    assert comparison.json()["best_offer"] is not None


def test_archive_job_flow(client):
    create = client.post(
        "/api/v1/catalog/books",
        json={"url": "https://www.buscalibre.com.co/libro-refactoring-isbn-9780134757599"},
    )
    assert create.status_code == 201

    create_job = client.post(
        "/api/v1/retention/jobs/archive",
        json={"older_than_days": 1, "min_active_records_per_book": 1},
    )
    assert create_job.status_code == 202
    job_id = create_job.json()["id"]

    job_status = client.get(f"/api/v1/retention/jobs/archive/{job_id}")
    assert job_status.status_code == 200
    assert job_status.json()["status"] in {"completed", "running", "queued"}
