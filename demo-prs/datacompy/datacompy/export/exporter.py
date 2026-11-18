"""Write the mismatched rows of a Snowflake comparison to S3, encrypted with KMS."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from locopy.logger import INFO, get_logger
from locopy.s3 import S3

from datacompy.export.config import S3_PREFIX, ExportConfig

if TYPE_CHECKING:
    from datacompy.snowflake import SnowflakeCompare

LOG = get_logger(__name__, INFO)


def build_key(compare: SnowflakeCompare, run_at: datetime) -> str:
    """Return the key for one export, e.g. ``mismatches/ORIG_vs_NEW/20261118T120000Z.csv``."""
    stamp = run_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{S3_PREFIX}{compare.df1_name}_vs_{compare.df2_name}/{stamp}.csv"


def export_mismatches(
    compare: SnowflakeCompare,
    config: ExportConfig,
    run_at: datetime | None = None,
) -> int:
    """Export the mismatched rows of a comparison that has run to one KMS-encrypted CSV.

    Sensitive columns are masked with the comparison's own
    ``hide_sensitive_columns`` before any row is read. The read is bounded by
    ``config.max_rows``, the file is uploaded once through locopy's
    ``S3.upload_to_s3``, and only counts are logged. Returns the number of
    rows exported; ``0`` means nothing was uploaded.

    Raises
    ------
    locopy.errors.S3UploadError
        If the upload fails.
    """
    if config.sensitive_columns:
        compare.hide_sensitive_columns(list(config.sensitive_columns))

    # all_mismatch() is a lazy Snowpark frame; limit() bounds the warehouse read.
    mismatches = compare.all_mismatch().limit(config.max_rows).to_pandas()
    if mismatches.empty:
        LOG.info("No mismatched rows to export")
        return 0

    key = build_key(compare, run_at or datetime.now(timezone.utc))
    with tempfile.TemporaryDirectory() as tmp:
        local_path = os.path.join(tmp, "mismatches.csv")
        mismatches.to_csv(local_path, index=False)
        S3(kms_key=config.kms_key_id).upload_to_s3(local_path, config.bucket, key)

    LOG.info("Exported %d mismatched rows (limit %d)", len(mismatches), config.max_rows)
    return len(mismatches)
