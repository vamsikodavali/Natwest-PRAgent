"""Tests for datacompy.export."""

import gzip
from unittest import mock

import pandas as pd
import pytest

from datacompy.export import ExportConfig, export_mismatches


def _compare(frame: pd.DataFrame, exported: tuple[str, ...] = ()) -> mock.Mock:
    compare = mock.Mock()
    compare.all_mismatch.return_value.to_pandas.return_value = frame
    runs = pd.DataFrame({"RUN_ID": list(exported)})
    compare.session.sql.return_value.to_pandas.return_value = runs
    return compare


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"join_key": ["k1", "k2"], "balance_df1": [10.0, 20.5], "balance_df2": [11.0, 20.0]}
    )


def test_object_key_rejects_unsafe_run_id():
    config = ExportConfig(bucket="bucket")
    assert config.object_key("run_42") == "mismatches/run_42/mismatches.csv.gz"
    with pytest.raises(ValueError):
        config.object_key("../other")


def test_prefix_gets_trailing_slash():
    assert ExportConfig(bucket="bucket", prefix="mismatches").prefix == "mismatches/"


def test_credentials_profile_precedence(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "default-profile")
    monkeypatch.setenv("DATACOMPY_EXPORT_AWS_PROFILE", "export-profile")
    assert ExportConfig(bucket="b").credentials_profile() == "export-profile"
    assert ExportConfig(bucket="b", aws_profile="x").credentials_profile() == "x"


@mock.patch("datacompy.export.exporter.S3")
def test_export_hides_columns_and_uploads_gzip(s3_cls):
    compare = _compare(_frame())
    config = ExportConfig(bucket="bucket", kms_key="kms-id", sensitive_columns=["tax_ref"])
    seen = {}

    def _upload(local, bucket, key):
        with gzip.open(local, "rt") as fh:
            seen["header"] = fh.readline().strip()

    s3_cls.return_value.upload_to_s3.side_effect = _upload
    url = export_mismatches(compare, config, "run_1")

    assert url == "s3://bucket/mismatches/run_1/mismatches.csv.gz"
    compare.hide_sensitive_columns.assert_called_once_with(["tax_ref"])
    s3_cls.assert_called_once_with(profile=mock.ANY, kms_key="kms-id")
    assert seen["header"] == "join_key,balance_df1,balance_df2"


@mock.patch("datacompy.export.exporter.S3")
def test_export_skips_upload_when_empty(s3_cls):
    compare = _compare(pd.DataFrame())
    assert export_mismatches(compare, ExportConfig(bucket="bucket"), "run_1") is None
    compare.hide_sensitive_columns.assert_not_called()
    s3_cls.assert_not_called()


@mock.patch("datacompy.export.exporter.S3")
def test_export_skips_run_already_exported(s3_cls):
    compare = _compare(_frame(), exported=("run_1",))
    assert export_mismatches(compare, ExportConfig(bucket="bucket"), "run_1") is None
    compare.all_mismatch.assert_not_called()
    s3_cls.assert_not_called()
