"""Write mismatched rows from a Snowflake comparison to S3."""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import tempfile

from locopy.s3 import S3

from datacompy.export.config import ExportConfig
from datacompy.snowflake import SnowflakeCompare

LOG = logging.getLogger(__name__)

EXPORTED_RUNS_QUERY = "SELECT * FROM DATACOMPY_RESULTS.PUBLIC.MISMATCH_EXPORTS"
RECORD_EXPORT_SQL = (
    "INSERT INTO DATACOMPY_RESULTS.PUBLIC.MISMATCH_EXPORTS (RUN_ID, S3_KEY, ROW_COUNT) "
    "VALUES (?, ?, ?)"
)


def export_mismatches(
    compare: SnowflakeCompare, config: ExportConfig, run_id: str
) -> str | None:
    """Export the mismatched rows of a finished comparison to S3.

    Sensitive columns are hidden with ``hide_sensitive_columns`` before any row
    is fetched. The rows are written to a gzip CSV in a temporary directory and
    uploaded through ``locopy.s3.S3.upload_to_s3``, which applies server-side
    encryption (AES256, or ``aws:kms`` when ``config.kms_key`` is set).

    Parameters
    ----------
    compare : SnowflakeCompare
        A comparison that has already run.
    config : ExportConfig
        Target bucket, prefix, encryption key and sensitive columns.
    run_id : str
        Identifier of the comparison run, used in the object key.

    Returns
    -------
    str or None
        The ``s3://`` URL of the uploaded file, or ``None`` when the run was
        already exported or had no mismatched rows.
    """
    key = config.object_key(run_id)
    exported = compare.session.sql(EXPORTED_RUNS_QUERY).to_pandas()
    if run_id in set(exported["RUN_ID"]):
        LOG.info("Run already exported, skipping")
        return None

    if config.sensitive_columns:
        compare.hide_sensitive_columns(config.sensitive_columns)

    frame = compare.all_mismatch().to_pandas()
    if frame.empty:
        LOG.info("No mismatched rows to export")
        return None

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = os.path.join(tmp, "mismatches.csv")
        gz_path = csv_path + ".gz"
        frame.to_csv(csv_path, index=False)
        with open(csv_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        uploader = S3(profile=config.credentials_profile(), kms_key=config.kms_key)
        uploader.upload_to_s3(gz_path, config.bucket, key)

    compare.session.sql(RECORD_EXPORT_SQL, params=[run_id, key, len(frame)]).collect()
    LOG.info(
        "Exported %d mismatched rows (%d columns, %d hidden)",
        len(frame),
        len(frame.columns),
        len(config.sensitive_columns),
    )
    return f"s3://{config.bucket}/{key}"
