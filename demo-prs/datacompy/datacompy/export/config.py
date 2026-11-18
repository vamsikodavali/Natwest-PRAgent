"""Configuration for the mismatch export."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class ExportConfig:
    """Where and how mismatched rows are exported.

    Parameters
    ----------
    bucket : str
        Target S3 bucket.
    prefix : str
        Key prefix inside the bucket. Defaults to ``mismatches/``.
    kms_key : str, optional
        KMS key id for ``aws:kms`` encryption. When omitted, uploads use AES256.
    sensitive_columns : list of str
        Columns hidden with ``hide_sensitive_columns`` before rows are fetched.
    aws_profile : str, optional
        Named AWS profile the uploader authenticates with.
    """

    bucket: str
    prefix: str = "mismatches/"
    kms_key: str | None = None
    sensitive_columns: list[str] = field(default_factory=list)
    aws_profile: str | None = None

    def __post_init__(self) -> None:
        if not self.bucket:
            raise ValueError("bucket is required")
        if not self.prefix.endswith("/"):
            object.__setattr__(self, "prefix", self.prefix + "/")

    @classmethod
    def from_env(cls, sensitive_columns: list[str] | None = None) -> ExportConfig:
        """Build a config from ``DATACOMPY_EXPORT_*`` environment variables."""
        return cls(
            bucket=os.environ.get("DATACOMPY_EXPORT_BUCKET", ""),
            prefix=os.environ.get("DATACOMPY_EXPORT_PREFIX", "mismatches/"),
            kms_key=os.environ.get("DATACOMPY_EXPORT_KMS_KEY_ID"),
            sensitive_columns=sensitive_columns or [],
            aws_profile=os.environ.get("DATACOMPY_EXPORT_AWS_PROFILE"),
        )

    def credentials_profile(self) -> str | None:
        """Return the AWS profile used to sign the upload.

        An explicit ``aws_profile`` wins, then ``DATACOMPY_EXPORT_AWS_PROFILE``,
        then ``AWS_PROFILE``. ``None`` lets boto3 use its default chain, for
        example an instance role.
        """
        return (
            self.aws_profile
            or os.environ.get("DATACOMPY_EXPORT_AWS_PROFILE")
            or os.environ.get("AWS_PROFILE")
        )

    def object_key(self, run_id: str) -> str:
        """Return ``<prefix><run_id>/mismatches.csv.gz`` for a validated run id."""
        if not _RUN_ID.match(run_id):
            raise ValueError("run_id must be 1-64 letters, digits, '_' or '-'")
        return f"{self.prefix}{run_id}/mismatches.csv.gz"
