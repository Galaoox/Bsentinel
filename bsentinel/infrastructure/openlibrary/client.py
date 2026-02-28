"""Cliente mínimo de OpenLibrary para enriquecimiento de libros."""

from __future__ import annotations

from typing import Any

import httpx

from bsentinel import settings


class OpenLibraryClient:
    async def enrich_by_isbn(self, isbn: str) -> dict[str, Any]:
        url = f"{settings.openlibrary_api_url}/api/books"
        params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
        try:
            async with httpx.AsyncClient(timeout=settings.scraping_timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
            payload = response.json()
        except Exception:
            return {}

        data = payload.get(f"ISBN:{isbn}") or {}
        subjects = [item.get("name") for item in data.get("subjects", []) if item.get("name")]
        return {
            "publisher": (data.get("publishers") or [{}])[0].get("name"),
            "publication_year": self._safe_year(data.get("publish_date")),
            "language": self._extract_language(data),
            "pages": data.get("number_of_pages"),
            "description": self._extract_description(data),
            "image_url": (data.get("cover") or {}).get("medium"),
            "categories": subjects[:10],
        }

    @staticmethod
    def _extract_language(data: dict[str, Any]) -> str | None:
        languages = data.get("languages") or []
        if not languages:
            return None
        key = languages[0].get("key")
        if not key:
            return None
        return key.split("/")[-1]

    @staticmethod
    def _extract_description(data: dict[str, Any]) -> str | None:
        description = data.get("description")
        if isinstance(description, dict):
            return description.get("value")
        if isinstance(description, str):
            return description
        return None

    @staticmethod
    def _safe_year(raw: Any) -> int | None:
        if not raw:
            return None
        text = str(raw)
        for token in text.replace(",", " ").split():
            if token.isdigit() and len(token) == 4:
                return int(token)
        return None
