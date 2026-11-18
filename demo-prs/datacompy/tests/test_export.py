"""Tests for the mismatch export."""

from __future__ import annotations

from unittest import mock

from datacompy.export import exporter
from datacompy.export.config import ExportSettings, load_settings
from datacompy.export.masking import mask_rows, mask_value


def test_mask_value_is_stable():
    assert mask_value("a@b.com") == mask_value("a@b.com")
    assert mask_value("a@b.com") != mask_value("c@d.com")


def test_mask_rows_only_touches_sensitive_columns():
    rows = [{"customer_id": 7, "amount": 12}]
    out = mask_rows(rows, ("customer_id",))
    assert out[0]["amount"] == 12
    assert out[0]["customer_id"] != 7


def test_load_settings_overrides(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("bucket: other\nmax_rows: 5\n")
    settings = load_settings(str(cfg))
    assert settings.bucket == "other"
    assert settings.max_rows == 5


def test_export_uploads_one_key_per_row():
    rows = [{"customer_id": 1, "email": "a@b.com", "amount": 3}]
    with (
        mock.patch.object(exporter, "fetch_mismatches", return_value=rows),
        mock.patch.object(exporter, "make_client", return_value=mock.Mock()),
        mock.patch.object(exporter, "upload_file", return_value="mismatches/row_0.csv"),
        mock.patch.object(exporter, "notify_done"),
    ):
        assert exporter.export_mismatches() == ["mismatches/row_0.csv"]


def test_default_prefix():
    assert ExportSettings().prefix == "mismatches/"
