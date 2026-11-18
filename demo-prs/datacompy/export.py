"""Export datacompy mismatch results to S3 for analysts to investigate."""

import csv
import logging
import tempfile

from locopy.s3 import S3

LOG = logging.getLogger(__name__)

MAX_ROWS = 100_000
COLUMNS = ("row_id", "column_name", "base_value", "compare_value")


def export_mismatches(cursor, table, bucket, kms_key):
    """Write the mismatched rows to one CSV and upload it, KMS-encrypted, under mismatches/.

    Credentials come from the default boto3 chain (environment or IAM role),
    never from code. Only row counts are logged.
    """
    if not table.isidentifier():
        raise ValueError(f"unexpected table name: {table!r}")
    if not kms_key:
        raise ValueError("kms_key is required: mismatch exports must be encrypted with KMS")

    cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM {table} LIMIT %s", (MAX_ROWS,))
    rows = cursor.fetchall()

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        writer.writerows(rows)

    S3(kms_key=kms_key).upload_to_s3(fh.name, bucket, f"mismatches/{table}.csv")
    LOG.info("Exported %d mismatched rows from %s", len(rows), table)
    return len(rows)
