import json

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

SUSPICIOUS_INTERSTITIAL_HTML = """
<html>
  <head><title>Just a moment...</title></head>
  <body>
    <div class="cf-challenge">Checking your browser before accessing Buscalibre</div>
    <p>Please wait while we verify your connection is secure.</p>
  </body>
</html>
"""

SUSPICIOUS_NON_PRODUCT_HTML = """
<html>
  <head><title>Buscalibre</title></head>
  <body>
    <main>
      <h1>We need to verify your request</h1>
      <p>Enable JavaScript and cookies to continue.</p>
    </main>
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


class FailingHttpSession:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[str] = []

    async def fetch(self, url: str) -> Response:
        self.calls.append(url)
        raise self.error


class SequencedSession:
    def __init__(self, responses: list[Response]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    async def fetch(self, url: str) -> Response:
        self.calls.append(url)
        if not self._responses:
            raise AssertionError("No more queued responses")
        return self._responses.pop(0)


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
@pytest.mark.parametrize("product_types", [["Product", "Book"], ["Book", "Product"]])
async def test_configured_scraper_extracts_multi_typed_book_without_transient_retries(product_types):
    product = {
        "@context": "https://schema.org/",
        "@type": product_types,
        "name": "VOCES DE CHERNOBIL (EDICION ESPECIAL EN TAPA DURA)",
        "isbn": "9788466387590",
        "author": {"@type": "Person", "name": "Alexievich Svetlana"},
        "offers": [{"price": "58650.00", "availability": "http://schema.org/InStock"}],
    }
    body = (
        '<html><head><script type="application/ld+json">'
        + json.dumps({"@type": "WebSite", "name": "Buscalibre"})
        + '</script><script type="application/ld+json">'
        + json.dumps(product)
        + '</script></head><body><h1>Fallback title</h1></body></html>'
    )
    session = SequencedSession([build_response(body), build_response(body)])
    scraper = ConfiguredStoreScraper(browser_session=session, transient_retry_delay_ms=0)
    store = Store(extraction_rules=build_default_buscalibre_rules())
    url = "https://www.buscalibre.com.co/libro-voces-de-chernobil"

    details = await scraper.extract_book_details(store, url)
    result = await scraper.scrape_book(store, url)

    assert details.title == product["name"]
    assert details.authors == ["Alexievich Svetlana"]
    assert details.isbn == "9788466387590"
    assert result.price == 58650.0
    assert result.status == "activo"
    assert session.calls == [url, url]


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


def test_validate_page_response_rejects_short_202_html_as_interstitial():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response("", status=202)

    with pytest.raises(ScrapingError, match="fetch_interstitial"):
        scraper._validate_page_response(store, "https://www.buscalibre.com.co/libro-iliada", response)


def test_validate_page_response_rejects_non_html_content_type():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response('{"ok": true}', content_type="application/json")

    with pytest.raises(ScrapingError, match="unexpected_content_type"):
        scraper._validate_page_response(store, "https://www.buscalibre.com.co/libro-iliada", response)


def test_classify_page_response_marks_long_202_html_as_transient_suspicious():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())
    response = build_response(SUSPICIOUS_INTERSTITIAL_HTML, status=202)

    classification = scraper._classify_page_response(store, response)

    assert classification.kind == "transient_suspicious"
    assert classification.reason == "fetch_interstitial"
    assert classification.signals["status_code"] == 202
    assert classification.signals["challenge_detected"] is True


def test_classify_page_response_marks_short_202_html_as_transient_suspicious():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    classification = scraper._classify_page_response(store, build_response("", status=202))

    assert classification.kind == "transient_suspicious"
    assert classification.reason == "fetch_interstitial"
    assert classification.signals["status_code"] == 202
    assert classification.signals["body_length"] == 0


def test_classify_page_response_keeps_real_product_page_usable():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    classification = scraper._classify_page_response(store, build_response(HTML))

    assert classification.kind == "usable"
    assert classification.reason == "usable"
    assert classification.signals["product_json_ld_found"] is True
    assert classification.signals["product_signal_count"] >= 1


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
async def test_extract_book_details_keeps_authors_not_found_for_usable_page_missing_author():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(HTML_WITHOUT_AUTHORS)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-sin-autor")

    assert exc_info.value.reason == "authors_not_found"
    assert exc_info.value.diagnostics["product_json_ld_found"] is True
    assert exc_info.value.diagnostics["attempted_sources"] == 2


@pytest.mark.asyncio
async def test_extract_book_details_reports_retry_exhaustion_for_suspicious_non_product_page():
    scraper = ConfiguredStoreScraper(browser_session=StubBrowserSession(build_response(SUSPICIOUS_NON_PRODUCT_HTML)))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-invalido")

    assert exc_info.value.reason == "interstitial_transient_exhausted"
    assert exc_info.value.diagnostics["classification"] == "transient_suspicious"
    assert exc_info.value.diagnostics["transient_attempts"] == 3
    assert exc_info.value.diagnostics["product_signal_count"] < 2
    assert exc_info.value.diagnostics["authors_found"] is False
    assert exc_info.value.diagnostics["product_json_ld_found"] is False


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


@pytest.mark.asyncio
async def test_http_failure_remains_http_failure_without_browser_fallback(monkeypatch: pytest.MonkeyPatch):
    browser_start_calls = {"count": 0}

    async def fake_browser_start(self) -> None:
        browser_start_calls["count"] += 1

    monkeypatch.setattr(StealthBrowserSession, "start", fake_browser_start)
    scraper = ConfiguredStoreScraper(browser_session=FailingHttpSession(TimeoutError("proxy timeout")))
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-iliada")

    assert exc_info.value.reason == "fetch_failed"
    assert exc_info.value.diagnostics["error_type"] == "TimeoutError"
    assert browser_start_calls["count"] == 0


@pytest.mark.asyncio
async def test_fetch_page_retries_transient_suspicious_response_until_page_becomes_usable():
    session = SequencedSession(
        [
            build_response(SUSPICIOUS_INTERSTITIAL_HTML, status=202),
            build_response(HTML),
        ]
    )
    scraper = ConfiguredStoreScraper(
        browser_session=session,
        transient_retry_attempts=2,
        transient_retry_delay_ms=0,
    )
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    details = await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-tdd")

    assert details.title == "Test Driven Development"
    assert details.authors == ["Kent Beck"]
    assert session.calls == [
        "https://www.buscalibre.com.co/libro-tdd",
        "https://www.buscalibre.com.co/libro-tdd",
    ]


@pytest.mark.asyncio
async def test_fetch_page_reports_interstitial_exhaustion_after_bounded_transient_retries():
    session = SequencedSession(
        [
            build_response(SUSPICIOUS_INTERSTITIAL_HTML, status=202),
            build_response(SUSPICIOUS_NON_PRODUCT_HTML, status=202),
            build_response(SUSPICIOUS_INTERSTITIAL_HTML, status=202),
        ]
    )
    scraper = ConfiguredStoreScraper(
        browser_session=session,
        transient_retry_attempts=2,
        transient_retry_delay_ms=0,
    )
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-interstitial")

    assert exc_info.value.reason == "interstitial_transient_exhausted"
    assert exc_info.value.diagnostics["classification"] == "transient_suspicious"
    assert exc_info.value.diagnostics["transient_attempts"] == 3
    assert exc_info.value.diagnostics["last_classification"] == "transient_suspicious"
    assert exc_info.value.diagnostics["last_reason"] == "fetch_interstitial"
    assert session.calls == [
        "https://www.buscalibre.com.co/libro-interstitial",
        "https://www.buscalibre.com.co/libro-interstitial",
        "https://www.buscalibre.com.co/libro-interstitial",
    ]


@pytest.mark.asyncio
async def test_fetch_page_does_not_retry_invalid_fetch_response():
    session = SequencedSession([build_response('{"ok": true}', content_type="application/json")])
    scraper = ConfiguredStoreScraper(
        browser_session=session,
        transient_retry_attempts=2,
        transient_retry_delay_ms=0,
    )
    store = Store(domain="www.buscalibre.com.co", extraction_rules=build_default_buscalibre_rules())

    with pytest.raises(ScrapingError) as exc_info:
        await scraper.extract_book_details(store, "https://www.buscalibre.com.co/libro-json")

    assert exc_info.value.reason == "unexpected_content_type"
    assert exc_info.value.diagnostics["classification"] == "invalid_fetch"
    assert session.calls == ["https://www.buscalibre.com.co/libro-json"]
