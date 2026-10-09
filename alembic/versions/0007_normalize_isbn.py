"""Normalize unambiguous ISBNs and known default extraction patterns.

Spelling changes cannot be reversed: restore a pre-upgrade backup to recover them.
"""

import logging
import re
from collections import defaultdict
from copy import deepcopy

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_normalize_isbn"
down_revision = "0006_add_panamericana_store"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")
OLD_PATTERNS = {r"(97[89]\d{10}|\d{9}[\dXx])", r"\b(97[89]\d{10}|\d{9}[\dXx])\b"}
ISBN_REGEX = r"(?<![0-9Xx])((?:97[89][\s-]*(?:[0-9][\s-]*){9}[0-9])|(?:[0-9][\s-]*){9}[0-9Xx])(?![0-9Xx])"


def _normalize(value):
    # Frozen migration algorithm: never import the evolving application validator.
    if not value:
        return None
    isbn = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        digits = [10 if char == "X" else int(char) for char in isbn]
        return isbn if sum((10 - i) * digit for i, digit in enumerate(digits)) % 11 == 0 else None
    if re.fullmatch(r"97[89][0-9]{10}", isbn):
        return isbn if sum(int(char) * (1 if i % 2 == 0 else 3) for i, char in enumerate(isbn)) % 10 == 0 else None
    return None


def upgrade() -> None:
    bind = op.get_bind()
    books = sa.table("books", sa.column("id", sa.String()), sa.column("isbn", sa.String()))
    groups = defaultdict(list)
    report = {"normalized": [], "conflict": [], "invalid": [], "empty": []}
    for row in bind.execute(sa.select(books)).mappings():
        normalized = _normalize(row["isbn"])
        if normalized:
            groups[normalized].append(row)
        else:
            report["empty" if not row["isbn"] or not row["isbn"].strip() else "invalid"].append(row["id"])
    for normalized, rows in groups.items():
        if len(rows) > 1:
            report["conflict"].extend(row["id"] for row in rows)
        elif rows[0]["isbn"] != normalized:
            bind.execute(books.update().where(books.c.id == rows[0]["id"]).values(isbn=normalized))
            report["normalized"].append(rows[0]["id"])
    for reason, ids in report.items():
        logger.warning("ISBN migration reason=%s count=%d book_ids=%s", reason, len(ids), ids)

    json_type = postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()
    stores = sa.table("stores", sa.column("id", sa.String()), sa.column("extraction_rules", json_type))
    for row in bind.execute(sa.select(stores)).mappings():
        rules = deepcopy(row["extraction_rules"] or {})
        changed = False
        for source in rules.get("isbn", {}).get("sources", []):
            if (source.get("kind") == "css" and source.get("selector") == "body"
                    and source.get("attribute") == "text" and source.get("normalizer") == "isbn_digits"
                    and source.get("regex") in OLD_PATTERNS):
                source["regex"] = ISBN_REGEX
                changed = True
        if changed:
            bind.execute(stores.update().where(stores.c.id == row["id"]).values(extraction_rules=rules))


def downgrade() -> None:
    # No data reconstruction: spelling and previous default patterns are not retained.
    pass
