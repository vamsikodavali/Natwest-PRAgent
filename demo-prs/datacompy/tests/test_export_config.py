import pytest

from datacompy.export import ExportConfig
from datacompy.export.config import DEFAULT_MAX_ROWS

BASE_ENV = {
    "DATACOMPY_EXPORT_BUCKET": "analytics-exports",
    "DATACOMPY_EXPORT_KMS_KEY_ID": "alias/mismatch-export",
    "DATACOMPY_EXPORT_SENSITIVE_COLUMNS": "account_ref, customer_ref,",
}


def test_from_env_reads_settings():
    config = ExportConfig.from_env(BASE_ENV)

    assert config.bucket == "analytics-exports"
    assert config.kms_key_id == "alias/mismatch-export"
    assert config.sensitive_columns == ("account_ref", "customer_ref")
    assert config.max_rows == DEFAULT_MAX_ROWS


def test_from_env_requires_kms_key():
    env = {**BASE_ENV, "DATACOMPY_EXPORT_KMS_KEY_ID": ""}

    with pytest.raises(ValueError, match="kms_key_id is required"):
        ExportConfig.from_env(env)


def test_from_env_requires_sensitive_columns_to_be_declared():
    env = {k: v for k, v in BASE_ENV.items() if k != "DATACOMPY_EXPORT_SENSITIVE_COLUMNS"}

    with pytest.raises(ValueError, match="SENSITIVE_COLUMNS must be set"):
        ExportConfig.from_env(env)


@pytest.mark.parametrize("max_rows", ["0", "1000001"])
def test_from_env_rejects_unbounded_or_empty_limit(max_rows):
    env = {**BASE_ENV, "DATACOMPY_EXPORT_MAX_ROWS": max_rows}

    with pytest.raises(ValueError, match="max_rows must be between"):
        ExportConfig.from_env(env)
