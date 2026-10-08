"""Canonical ISBN spelling and checksum validation, without edition conversion."""

import re


def normalize_isbn(value: str | None) -> str | None:
    if not value:
        return None
    isbn = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        digits = [10 if char == "X" else int(char) for char in isbn]
        return isbn if sum((10 - index) * digit for index, digit in enumerate(digits)) % 11 == 0 else None
    if re.fullmatch(r"97[89][0-9]{10}", isbn):
        return isbn if sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(isbn)) % 10 == 0 else None
    return None
