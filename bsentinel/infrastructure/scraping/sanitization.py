"""Helpers to redact proxy credentials from observable output."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_PROXY_CREDENTIALS_RE = re.compile(r"(?P<scheme>[a-z][a-z0-9+\-.]*://)(?P<user>[^:@/\s]+)(?::(?P<password>[^@/\s]*))?@", re.IGNORECASE)


def sanitize_proxy_credentials(value: str) -> str:
    return _PROXY_CREDENTIALS_RE.sub(r"\g<scheme>***:***@", value)


def sanitize_proxy_observable(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_proxy_credentials(value)
    if isinstance(value, Mapping):
        return {key: sanitize_proxy_observable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(sanitize_proxy_observable(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_proxy_observable(item) for item in value]
    return value
