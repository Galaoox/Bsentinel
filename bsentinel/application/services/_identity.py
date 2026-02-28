"""Book identity helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

ISBN_PATTERN = re.compile(r"\b(97[89]\d{10}|\d{9}[\dXx])\b")


def extract_book_identity(product_url: str) -> tuple[str, list[str], str | None]:
    parsed = urlparse(product_url)
    query = parse_qs(parsed.query)

    isbn = None
    if query.get("isbn"):
        isbn = query["isbn"][0]
    else:
        match = ISBN_PATTERN.search(product_url)
        if match:
            isbn = match.group(1)

    slug = parsed.path.strip("/").split("/")[-1] or "book"
    title = slug.replace("-", " ").strip().title()
    if not title:
        title = "Untitled Book"

    return title, ["Unknown Author"], isbn
