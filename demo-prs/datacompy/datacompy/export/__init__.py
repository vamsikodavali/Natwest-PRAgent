"""Export mismatched rows from a Snowflake comparison to S3."""

from datacompy.export.config import ExportConfig
from datacompy.export.exporter import export_mismatches

__all__ = ["ExportConfig", "export_mismatches"]
