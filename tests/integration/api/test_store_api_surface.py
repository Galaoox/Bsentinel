def test_store_routes_are_not_exposed_in_mvp_api_surface(client):
    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    openapi_payload = openapi_response.json()
    assert "/api/v1/stores" not in openapi_payload["paths"]

    for method in ("get", "post"):
        response = getattr(client, method)("/api/v1/stores")
        assert response.status_code == 404
