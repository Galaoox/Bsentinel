import pytest
from scrapling.engines.toolbelt.custom import Response

from bsentinel.domain.models import Store
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.scraping import configured as configured_module
from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
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

HTML_WITHOUT_AUTHORS = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "South of the Border, West of the Sun",
        "isbn": "9786287577107",
        "offers": {"price": "59.900", "availability": "https://schema.org/InStock"}
      }
    </script>
  </head>
  <body>
    <h1>South of the Border, West of the Sun</h1>
  </body>
</html>
"""


HTML_WITH_DOT_DECIMAL_PRICE = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Kafka on the Shore",
        "isbn": "9781400079278",
        "author": [{"name": "Haruki Murakami"}],
        "offers": {"price": "41850.00", "availability": "https://schema.org/InStock"}
      }
    </script>
  </head>
</html>
"""


class StubBrowserSession:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[str] = []

    async def fetch(self, url: str) -> Response:
        self.calls.append(url)
        return self.response


def build_response(
    body: str,
    *,
    status: int = 200,
    content_type: str = "text/html; charset=utf-8",
    url: str = "https://www.buscalibre.com.co/libro-iliada",
) -> Response:
    return Response(
        url=url,
        content=body,
        status=status,
        reason="OK",
        cookies={},
        headers={"content-type": content_type},
        request_headers={},
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_configured_scraper_extracts_details_from_json_ld():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(extraction_rules=build_default_buscalibre_rules())

    details = await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-tdd")

    assert details.title == "Test Driven Development"
    assert details.authors == ["Kent Beck"]
    assert details.isbn == "9780321146533"


@pytest.mark.asyncio
async def test_configured_scraper_extracts_price_and_status():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(extraction_rules=build_default_buscalibre_rules())

    result = await scraper.scrape_book(store, "https://www.buscalibre.com.co/libro-tdd")

    assert result.price == 45900.0
    assert result.status == "activo"


@pytest.mark.asyncio
async def test_configured_scraper_keeps_dot_decimal_price_without_multiplying_by_100():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML_WITH_DOT_DECIMAL_PRICE)))
    store = Store(extraction_rules=build_default_buscalibre_rules())

    result = await scraper.scrape_book(store, "https://www.buscalibre.com.co/libro-kafka-on-the-shore")

    assert result.price == 41850.0


def test_price_normalizers_parse_expected_formats():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))

    assert scraper._normalize_value("price_cop_mixed", "41850.00") == 41850.0
    assert scraper._normalize_value("price_cop_mixed", "41.850,00") == 41850.0
    assert scraper._normalize_value("price_cop", "41.850") == 41850.0
    assert scraper._normalize_value("price_decimal", "41850.50") == 41850.5
    assert scraper._normalize_value("price_latam", "41850.00") == 41850.0


def test_price_normalizers_return_none_for_invalid_values():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))

    assert scraper._normalize_value("price_decimal", "price unavailable") is None
    assert scraper._normalize_value("price_cop", "41850.50") is None


def test_validate_page_response_rejects_empty_body():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response("")

    with pytest.raises(ScrapingError, match="empty_body"):
        scraper._validate_page_response(store, "https://www.buscalibre.com.co/libro-iliada", response)


def test_validate_page_response_rejects_accepted_without_html():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response("", status=202)

    with pytest.raises(ScrapingError, match="accepted_without_html"):
        scraper._validate_page_response(store, "https://www.buscalibre.com.co/libro-iliada", response)


def test_validate_page_response_rejects_non_html_content_type():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response('{"ok": true}', content_type="application/json")

    with pytest.raises(ScrapingError, match="unexpected_content_type"):
        scraper._validate_page_response(store, "https://www.buscalibre.com.co/libro-iliada", response)


@pytest.mark.asyncio
async def test_extract_book_details_logs_attempts_when_authors_are_missing(monkeypatch: pytest.MonkeyPatch):
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML_WITHOUT_AUTHORS)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    captured: dict[str, object] = {}

    def fake_warning(message: str, *, extra: dict[str, object]) -> None:
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr(configured_module.logger, "warning", fake_warning)

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(
            store, "https://www.buscalibre.com.co/libro-al-sur-de-la-frontera-al-oeste-del-sol"
        )

    assert exc_info.value.reason == "authors_not_found"
    assert exc_info.value.diagnostics["field_name"] == "authors"
    assert exc_info.value.diagnostics["attempted_sources"] == 2
    assert exc_info.value.diagnostics["product_json_ld_found"] is True
    assert captured["message"] == "Scraping field extraction failed"
    assert captured["extra"] == exc_info.value.diagnostics


@pytest.mark.asyncio
async def test_fetch_page_raises_when_browser_session_is_not_initialized():
    browser_session = StealthBrowserSession(
        headless=True,
        timeout_ms=45000,
        max_pages=3,
        disable_resources=True,
        network_idle=True,
        solve_cloudflare=False,
        real_chrome=False,
    )
    scraper = ConfiguredStoreScraper(browser_session=browser_session)
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-iliada")

    assert exc_info.value.reason == "fetch_failed"
    assert exc_info.value.diagnostics["error_type"] == "RuntimeError"
