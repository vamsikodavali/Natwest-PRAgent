# Mismatch export

After a comparison runs against Snowflake, `datacompy.export.export_mismatches`
writes the mismatched rows to S3 so analysts can investigate them.

## Usage

```python
from datacompy.export import export_mismatches

keys = export_mismatches("export.yaml")
```

## Settings

Settings come from an optional YAML file. Supported keys:

| Key | Meaning |
|---|---|
| `bucket` | Destination S3 bucket |
| `prefix` | Key prefix, default `mismatches/` |
| `region` | AWS region |
| `sensitive_columns` | Columns hashed before export |
| `webhook_url` | Optional completion webhook |

## Output

One CSV per mismatched row is uploaded under `mismatches/`. Sensitive columns
are hashed. A message is posted to the webhook when the export finishes.

## Warehouse

`infra/export_warehouse.sql` creates the `DC_EXPORT_WH` warehouse used by the job.
