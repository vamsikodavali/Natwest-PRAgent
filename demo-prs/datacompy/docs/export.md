# Mismatch export

After a Snowflake comparison, `datacompy.export` copies the mismatched rows to
S3 so analysts can investigate them outside the warehouse.

## Usage

```python
from datacompy import SnowflakeCompare
from datacompy.export import ExportConfig, export_mismatches

compare = SnowflakeCompare(session, "PROD.LEDGER", "UAT.LEDGER", join_columns=["id"])
config = ExportConfig.from_env(sensitive_columns=["tax_ref", "account_number"])
url = export_mismatches(compare, config, run_id="2026_11_18_nightly")
```

## Configuration

| Variable | Purpose |
|---|---|
| `DATACOMPY_EXPORT_BUCKET` | Target bucket (required) |
| `DATACOMPY_EXPORT_PREFIX` | Key prefix, default `mismatches/` |
| `DATACOMPY_EXPORT_KMS_KEY_ID` | KMS key for `aws:kms`; AES256 when unset |
| `DATACOMPY_EXPORT_AWS_PROFILE` | AWS profile for the upload, falls back to `AWS_PROFILE` |

## What leaves the process

- One gzip CSV per run at `<prefix><run_id>/mismatches.csv.gz`, encrypted at rest.
- Columns in `sensitive_columns` are hidden with `hide_sensitive_columns` first.
- Logs carry row and column counts only.

Run `infra/export_warehouse.sql` once per account before the first export.
