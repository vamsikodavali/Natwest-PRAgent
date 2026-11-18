"""Upload helpers for exported files."""

from __future__ import annotations

import boto3

from datacompy.export.config import ExportSettings


def make_client(settings: ExportSettings):
    """Create an S3 client from the export settings."""
    return boto3.client(
        "s3",
        region_name=settings.region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def upload_file(client, settings: ExportSettings, local_path: str, name: str) -> str:
    """Upload one local file under the export prefix and return its S3 key."""
    key = f"{settings.prefix}{name}"
    client.upload_file(local_path, settings.bucket, key)
    return key
