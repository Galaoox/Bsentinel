def test_openapi_declares_expected_tags_metadata(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()

    tag_names = [tag["name"] for tag in payload.get("tags", [])]
    assert tag_names == ["Root", "Health", "system", "catalog", "pricing", "retention"]


def test_openapi_v1_operations_do_not_include_version_tag(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()

    for path, methods in payload.get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            continue
        for spec in methods.values():
            if not isinstance(spec, dict):
                continue
            assert "v1" not in spec.get("tags", [])


def test_openapi_groups_v1_endpoints_by_controller_tags(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    paths = payload["paths"]

    assert paths["/api/v1/system/info"]["get"]["tags"] == ["system"]
    assert paths["/api/v1/catalog/books"]["post"]["tags"] == ["catalog"]
    assert paths["/api/v1/pricing/books/{book_id}/history"]["get"]["tags"] == ["pricing"]
    assert paths["/api/v1/retention/jobs/archive"]["post"]["tags"] == ["retention"]
