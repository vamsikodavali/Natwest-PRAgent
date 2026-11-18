"""Export the mismatched rows of a comparison to S3 for investigation."""

from datacompy.export.config import ExportConfig
from datacompy.export.exporter import export_mismatches

__all__ = ["ExportConfig", "export_mismatches"]
