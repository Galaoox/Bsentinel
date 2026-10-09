"""Instance-local Scrapling 0.4.2/curl_cffi 0.14 transport hook.

No global patching. One event per curl request, including Scrapling retries.
Redirect body counters are not a complete redirect-chain measurement.
"""

import asyncio
import logging
from ipaddress import ip_address
from urllib.parse import urlsplit

from curl_cffi import CurlInfo
from curl_cffi.curl import CurlError

from bsentinel.application.services.traffic_context import attribution
from bsentinel.domain.traffic import TrafficEvent
from bsentinel.infrastructure.scraping.sanitization import sanitize_proxy_credentials
from bsentinel.infrastructure.scraping.store_guard import check_periodic_admission, fetch_admission

logger = logging.getLogger(__name__)
missing_writes = 0
unobserved_fetches = 0
COUNTERS = (
    CurlInfo.SIZE_DOWNLOAD_T,
    CurlInfo.SIZE_UPLOAD_T,
    CurlInfo.REQUEST_SIZE,
    CurlInfo.HEADER_SIZE,
    CurlInfo.REDIRECT_COUNT,
)


async def discard_event(event):
    return None


def instrument_transport(session, sink=discard_event):
    global unobserved_fetches
    transport = getattr(session, "_async_curl_session", None)
    if transport is None:
        unobserved_fetches += 1
        logger.warning("Traffic hook unavailable", extra={"traffic_completeness": "missing"})
        return False
    transport.curl_infos = list(dict.fromkeys([*getattr(transport, "curl_infos", []), *COUNTERS]))
    request = transport.request

    async def measured_request(*args, **kwargs):
        global missing_writes
        check_periodic_admission()
        admission = fetch_admission.get()
        if admission is not None:
            # Before every real transport attempt, including internal network retries.
            # A no-request rejection produces no synthetic zero-byte event.
            await admission.guard.check(admission.store)
        # SQL pause reads may cross the hard cohort deadline. No await between
        # this final time check and invoking the actual transport attempt.
        check_periodic_admission()
        response = None
        outcome = "failed"
        try:
            response = await request(*args, **kwargs)
            outcome = "successful" if response.status_code < 400 else "http_error"
            return response
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except CurlError as exc:
            response = getattr(exc, "response", None)
            # Scrapling logs/retries this same error; preserve code and response.
            exc.args = tuple(sanitize_proxy_credentials(arg) if isinstance(arg, str) else arg
                             for arg in exc.args)
            raise
        except Exception as exc:
            response = getattr(exc, "response", None)
            raise
        finally:
            infos = getattr(response, "infos", {}) or {}
            sizes = [infos.get(info) for info in COUNTERS]
            sizes = [int(v) if isinstance(v, (int, float)) and v >= 0 else None for v in sizes]
            completeness = "known" if all(v is not None for v in sizes) else "unknown"
            if sizes[-1] or (completeness == "unknown" and any(v is not None for v in sizes)):
                completeness = "incomplete"
            url = kwargs.get("url", args[1] if len(args) > 1 else "")
            domain = urlsplit(url).hostname or "unknown"
            try:
                ip_address(domain)
            except ValueError:
                pass
            else:
                domain = "unknown"
            event = TrafficEvent(
                domain=domain,
                outcome=outcome,
                http_status=getattr(response, "status_code", None),
                download_bytes=sizes[0],
                upload_bytes=sizes[1],
                request_bytes=sizes[2],
                header_bytes=sizes[3],
                redirects=sizes[4],
                completeness=completeness,
                **attribution.get(),
            )
            try:
                await asyncio.wait_for(sink(event), timeout=5)
            except Exception:
                missing_writes += 1
                # No exception strings: SQL/HTTP errors can contain credentials.
                logger.warning(
                    "Traffic persistence missing",
                    extra={"event_id": event.id, "traffic_completeness": "missing"},
                )

    transport.request = measured_request
    return True
