"""Default extraction rules for supported stores."""

from __future__ import annotations

from copy import deepcopy

_DEFAULT_BUSCALIBRE_RULES = {
    "title": {
        "sources": [
            {"kind": "json_ld", "path": "name", "normalizer": "text_trim"},
            {"kind": "css", "selector": "h1", "attribute": "text", "normalizer": "text_trim"},
            {
                "kind": "css",
                "selector": "meta[property='og:title']",
                "attribute": "content",
                "normalizer": "text_trim",
            },
        ]
    },
    "authors": {
        "sources": [
            {"kind": "json_ld", "path": "author[].name", "normalizer": "text_trim"},
            {"kind": "css", "selector": ".author a", "attribute": "text", "normalizer": "text_trim"},
        ]
    },
    "isbn": {
        "sources": [
            {"kind": "json_ld", "path": "isbn", "normalizer": "isbn_digits"},
            {"kind": "css", "selector": "body", "attribute": "text", "regex": "(97[89]\\d{10}|\\d{9}[\\dXx])", "normalizer": "isbn_digits"},
        ]
    },
    "price": {
        "sources": [
            {"kind": "json_ld", "path": "offers[].price", "normalizer": "price_latam"},
            {
                "kind": "css",
                "selector": "meta[property='product:price:amount']",
                "attribute": "content",
                "normalizer": "price_latam",
            },
            {"kind": "css", "selector": ".precio-ahora", "attribute": "text", "normalizer": "price_latam"},
        ]
    },
    "availability": {
        "sources": [
            {"kind": "json_ld", "path": "offers[].availability", "normalizer": "availability_buscalibre"},
            {"kind": "css", "selector": "body", "attribute": "text", "normalizer": "availability_buscalibre"},
        ]
    },
}


def build_default_buscalibre_rules() -> dict:
    return deepcopy(_DEFAULT_BUSCALIBRE_RULES)
