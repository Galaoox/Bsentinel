import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure local package import works under `uv run pytest` without editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bsentinel.infrastructure.api.root_app import in_memory_store, root_app


@pytest.fixture
def client():
    in_memory_store.reset()
    with TestClient(root_app) as test_client:
        yield test_client
    in_memory_store.reset()
