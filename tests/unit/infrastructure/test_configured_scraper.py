import pytest

from bsentinel.domain.models import Store
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
from bsentinel.infrastructure.scraping.rules import build_default_buscalibre_rules

HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Test Driven Development",
        "isbn": "9780321146533",
        "author": [{"name": "Kent Beck"}],
        "offers": {"price": "45.900", "availability": "https://schema.org/InStock"}
      }
    </script>
  </head>
  <body>
    <h1>Fallback Title</h1>
  </body>
</html>
"""


class StubConfiguredStoreScraper(ConfiguredStoreScraper):
    async def _fetch_html(self, store, product_url: str) -> str:  # type: ignore[override]
        return HTML


@pytest.mark.asyncio
async def test_configured_scraper_extracts_details_from_json_ld():
    scraper = StubConfiguredStoreScraper()
    store = Store(extraction_rules=build_default_buscalibre_rules())

    details = await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-tdd")

    assert details.title == "Test Driven Development"
    assert details.authors == ["Kent Beck"]
    assert details.isbn == "9780321146533"


@pytest.mark.asyncio
async def test_configured_scraper_extracts_price_and_status():
    scraper = StubConfiguredStoreScraper()
    store = Store(extraction_rules=build_default_buscalibre_rules())

    result = await scraper.scrape_book(store, "https://www.buscalibre.com.co/libro-tdd")

    assert result.price == 45900.0
    assert result.status == "activo"
