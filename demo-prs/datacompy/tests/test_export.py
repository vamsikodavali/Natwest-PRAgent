import logging
from datetime import datetime, timezone

import pandas as pd
import pytest

from datacompy.export import ExportConfig, export_mismatches
from datacompy.export import exporter

RUN_AT = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
ROW_VALUE = "ROW-VALUE-7731"


class FakeFrame:
    def __init__(self, data, calls):
        self.data = data
        self.calls = calls

    def limit(self, n):
        self.calls.append(("limit", n))
        return FakeFrame(self.data.head(n), self.calls)

    def to_pandas(self):
        return self.data


class FakeCompare:
    df1_name = "ORIGINAL"
    df2_name = "NEW"

    def __init__(self, data):
        self.data = data
        self.calls = []

    def hide_sensitive_columns(self, columns):
        self.calls.append(("hide", columns))

    def all_mismatch(self):
        self.calls.append(("all_mismatch",))
        return FakeFrame(self.data, self.calls)


class RecordingS3:
    uploads = []

    def __init__(self, kms_key=None):
        self.kms_key = kms_key

    def upload_to_s3(self, local, bucket, key):
        with open(local) as fh:
            RecordingS3.uploads.append((self.kms_key, bucket, key, fh.read()))


@pytest.fixture
def s3(monkeypatch):
    RecordingS3.uploads = []
    monkeypatch.setattr(exporter, "S3", RecordingS3)
    return RecordingS3


@pytest.fixture
def config():
    return ExportConfig(
        bucket="analytics-exports",
        kms_key_id="alias/mismatch-export",
        sensitive_columns=("ACCOUNT_REF",),
        max_rows=2,
    )


def mismatch_frame(n=3):
    return pd.DataFrame(
        {"ID": range(n), "ACCOUNT_REF_ORIGINAL": [ROW_VALUE] * n, "ACCOUNT_REF_NEW": ["x"] * n}
    )


def test_export_uploads_one_kms_encrypted_file_under_prefix(s3, config):
    rows = export_mismatches(FakeCompare(mismatch_frame()), config, run_at=RUN_AT)

    assert rows == 2
    assert len(s3.uploads) == 1
    kms_key, bucket, key, body = s3.uploads[0]
    assert kms_key == "alias/mismatch-export"
    assert bucket == "analytics-exports"
    assert key == "mismatches/ORIGINAL_vs_NEW/20261118T120000Z.csv"
    assert body.splitlines()[0] == "ID,ACCOUNT_REF_ORIGINAL,ACCOUNT_REF_NEW"


def test_export_masks_sensitive_columns_before_reading_rows(s3, config):
    compare = FakeCompare(mismatch_frame())

    export_mismatches(compare, config, run_at=RUN_AT)

    assert compare.calls[:3] == [("hide", ["ACCOUNT_REF"]), ("all_mismatch",), ("limit", 2)]


def test_export_without_mismatches_uploads_nothing(s3, config):
    assert export_mismatches(FakeCompare(mismatch_frame(0)), config, run_at=RUN_AT) == 0
    assert s3.uploads == []


def test_export_logs_counts_but_no_row_values_or_key(s3, config, caplog):
    with caplog.at_level(logging.DEBUG):
        export_mismatches(FakeCompare(mismatch_frame()), config, run_at=RUN_AT)

    assert "Exported 2 mismatched rows" in caplog.text
    assert ROW_VALUE not in caplog.text
    assert config.kms_key_id not in caplog.text
