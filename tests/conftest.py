import pytest
from fastapi.testclient import TestClient

from bsentinel.infrastructure.api.root_app import repository, root_app


@pytest.fixture
def client():
    repository.reset()
    with TestClient(root_app) as test_client:
        yield test_client
    repository.reset()
