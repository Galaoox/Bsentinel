import pytest
from pydantic import ValidationError

from bsentinel.infrastructure.api.v1 import schemas


def test_valid_bulk_request():
    model = schemas.CreateBooksBulkRequest(urls=["https://example.org/book"])
    assert model.urls == ["https://example.org/book"]


@pytest.mark.parametrize("urls", [[], ["x"] * 21, [1], [None], ["x", "x"], ["x" * 2049]])
def test_invalid_bulk_request(urls):
    with pytest.raises(ValidationError):
        schemas.CreateBooksBulkRequest(urls=urls)
