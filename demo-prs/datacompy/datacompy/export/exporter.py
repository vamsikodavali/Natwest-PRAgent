"""Query mismatched rows, write them to files and upload them."""

from __future__ import annotations

import csv
import logging
import os
import tempfile
from typing import Any

import snowflake.connector

from datacompy.export.config import ExportSettings, load_settings
from datacompy.export.masking import mask_rows
from datacompy.export.notify import notify_done
from datacompy.export.s3_uploader import make_client, upload_file

logger = logging.getLogger(__name__)

MISMATCH_QUERY = "SELECT * FROM ANALYTICS.PUBLIC.DATACOMPY_MISMATCHES"


def fetch_mismatches(settings: ExportSettings) -> list[dict[str, Any]]:
    """Read every row of the mismatch table."""
    try:
        conn = snowflake.connector.connect(settings.snowflake_dsn)
    except Exception as exc:
        raise RuntimeError(f"cannot connect with {settings.snowflake_dsn}") from exc
    cur = conn.cursor(snowflake.connector.DictCursor)
    try:
        cur.execute(MISMATCH_QUERY)
        return list(cur.fetchall())
    finally:
        cur.close()
        conn.close()


def write_csv(rows: list[dict[str, Any]], path: str) -> None:
    """Write rows to a CSV file with a header."""
    if not rows:
        return
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_mismatches(config_path: str | None = None) -> list[str]:
    """Export mismatched rows to S3 and return the uploaded keys."""
    settings = load_settings(config_path)
    rows = fetch_mismatches(settings)
    client = make_client(settings)
    keys: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, row in enumerate(rows):
            logger.info(
                "exporting mismatch %s customer_id=%s email=%s",
                i,
                row.get("customer_id"),
                row.get("email"),
            )
            safe = mask_rows([row], settings.sensitive_columns)
            path = os.path.join(tmp, f"row_{i}.csv")
            write_csv(safe, path)
            keys.append(upload_file(client, settings, path, f"row_{i}.csv"))
    notify_done(settings.webhook_url, len(keys), settings.prefix)
    return keys
