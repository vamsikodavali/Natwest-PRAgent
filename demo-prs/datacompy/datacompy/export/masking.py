"""Masking of sensitive columns before export."""

from __future__ import annotations

import hashlib
from typing import Any


def mask_value(value: Any) -> str:
    """Return a short stable hash for a single value."""
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()[:12]


def mask_rows(
    rows: list[dict[str, Any]], sensitive: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Replace the values of sensitive columns with their hash."""
    masked = []
    for row in rows:
        masked.append(
            {k: (mask_value(v) if k in sensitive else v) for k, v in row.items()}
        )
    return masked
