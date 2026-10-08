# Catalog creation: one usable store response

Individual `POST /api/v1/catalog/books` and sequential
`POST /api/v1/catalog/books/bulk` use `ScraperPort.extract_product`.
`ConfiguredStoreScraper` fetches/classifies one usable response and extracts
book identity, price and availability from that same response. The rule-driven
path applies to Buscalibre, Panamericana (including native VTEX properties),
and future configured adapters without store-specific double-fetch fallbacks.
The catalog's existing supported-domain allowlist is unchanged.

`ProductExtraction` contains only details and the timestamped price result, not
HTML or a response object. It belongs to one creation operation. There is no
URL cache, scraper-global last result, or shared request cache. Repeating a URL
in a later operation fetches fresh data; concurrent operations retain their own
values. OpenLibrary enrichment remains a separate provider call and does not
use the store/proxy transport.

The internal command returns `(book, relation, domain, result)` instead of three
values. Both creation callers explicitly pass that result to
`ScrapingService.record_result`, which never fetches. It saves the relation's
price/status/last_checked and exactly one initial history record with the same
checked timestamp inside the caller's existing transaction. Initial schedule
assignment, generation zero, hourly next-check calculation, duplicate checks,
canonical persistence URLs, original bulk response URLs, rollback and external
response schemas remain unchanged. No production migration is needed for this
change itself.

Creation rejects non-finite or negative extracted numeric prices before adding
a book or relation. Missing/unparseable price retains the existing configured
scraper behavior: zero with unknown status, or zero with out-of-stock status.
No new success claim is made for missing data. HTTP/content checks and required
metadata validation still fail normally before persistence.

"One response" means one usable page for both extraction purposes, not a
promise of exactly one HTTP attempt on errors. Existing bounded transient-page
and HTTP-transport retries are preserved. Transport metrics continue recording
all observed attempts, including failed retries and traffic from extractions
that later fail or transactions that roll back. Proxy routing and TLS safeguards
are unchanged. Manual/periodic refresh retains its existing single-price-fetch
path and independent transaction behavior.

Offline tests cover both public creation routes and stores, native VTEX identity,
mixed-store bulk rollback, invalid numeric prices, corrupted/empty/HTTP-error
responses, three concurrent operations, fresh repeated URLs, initial history and
calendar invariants, and real installed HTTP-library wiring with fixture
responses to verify per-attempt traffic attribution and explicit proxy routing.
Tests do not contact stores, OpenLibrary or a proxy. No scheduling change is
included; the current hourly schedule remains in place.
