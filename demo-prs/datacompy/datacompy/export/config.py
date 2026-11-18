"""Validated settings for exporting datacompy mismatches to S3."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

S3_PREFIX = "mismatches/"
DEFAULT_MAX_ROWS = 100_000
MAX_ROWS_CEILING = 1_000_000


@dataclass(frozen=True)
class ExportConfig:
    """Where a mismatch export goes and how much of it is written.

    ``kms_key_id`` is a key ARN or alias, not a secret. AWS credentials are
    never part of this config: boto3 resolves them from its default chain.
    ``sensitive_columns`` must be stated explicitly, even when empty.
    """

    bucket: str
    kms_key_id: str
    sensitive_columns: tuple[str, ...]
    max_rows: int = DEFAULT_MAX_ROWS

    def __post_init__(self) -> None:
        """Reject settings that would produce an unencrypted or unbounded export."""
        if not self.bucket:
            raise ValueError("bucket is required")
        if not self.kms_key_id:
            raise ValueError("kms_key_id is required: mismatch exports must use KMS")
        if not 1 <= self.max_rows <= MAX_ROWS_CEILING:
            raise ValueError(f"max_rows must be between 1 and {MAX_ROWS_CEILING}")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ExportConfig:
        """Build the config from ``DATACOMPY_EXPORT_*`` variables (default ``os.environ``)."""
        env = os.environ if environ is None else environ
        if "DATACOMPY_EXPORT_SENSITIVE_COLUMNS" not in env:
            raise ValueError(
                "DATACOMPY_EXPORT_SENSITIVE_COLUMNS must be set (comma-separated, may be empty)"
            )
        sensitive = env["DATACOMPY_EXPORT_SENSITIVE_COLUMNS"].split(",")
        return cls(
            bucket=env.get("DATACOMPY_EXPORT_BUCKET", ""),
            kms_key_id=env.get("DATACOMPY_EXPORT_KMS_KEY_ID", ""),
            sensitive_columns=tuple(c.strip() for c in sensitive if c.strip()),
            max_rows=int(env.get("DATACOMPY_EXPORT_MAX_ROWS", DEFAULT_MAX_ROWS)),
        )
