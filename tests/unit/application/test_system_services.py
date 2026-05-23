import pytest

from bsentinel.application.services import SystemQueryService
from bsentinel.domain.models import Store


class FakeStoreRepository:
    def __init__(self, stores):
        self._stores = stores

    async def list(self):
        return self._stores


@pytest.mark.asyncio
async def test_system_query_reports_buscalibre_only_even_with_extra_store_data():
    service = SystemQueryService(
        stores=FakeStoreRepository(
            [
                Store(domain="www.buscalibre.com.co"),
                Store(domain="www.demo.com"),
            ]
        )
    )

    info = await service.get_info()

    assert info["supported_sites"] == ["www.buscalibre.com.co"]


@pytest.mark.asyncio
async def test_system_query_reports_buscalibre_only_when_store_repo_is_empty():
    service = SystemQueryService(stores=FakeStoreRepository([]))

    info = await service.get_info()

    assert info["supported_sites"] == ["www.buscalibre.com.co"]
