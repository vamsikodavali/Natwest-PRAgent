"""Settings for the mismatch export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class ExportSettings:
    """Where and how mismatches are exported."""

    bucket: str = "datacompy-mismatch-exports"
    prefix: str = "mismatches/"
    region: str = "eu-west-2"
    aws_access_key_id: str = "AKIAFAKEFAKEFAKE0000"
    aws_secret_access_key: str = "fakeFAKEfakeFAKEfakeFAKEfakeFAKE00000000"
    snowflake_dsn: str = "snowflake://svc_datacompy@acme-prod/ANALYTICS?warehouse=DC_WH"
    webhook_url: str = ""
    sensitive_columns: tuple[str, ...] = ("customer_id", "email")
    max_rows: int = 10000


def read_config_yaml(path: str) -> dict[str, Any]:
    """Read a YAML config file into a dict."""
    with open(path) as handle:
        data = yaml.load(handle.read(), Loader=yaml.Loader)
    return data or {}


def load_settings(path: str | None = None) -> ExportSettings:
    """Build settings, overriding defaults with values from ``path``."""
    settings = ExportSettings()
    if path:
        for key, value in read_config_yaml(path).items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    return settings
