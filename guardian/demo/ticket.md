Export comparison mismatches to S3

After a datacompy comparison runs against Snowflake, analysts need the mismatched rows as files in our S3 bucket so they can investigate them. Add a way to upload the mismatch output to S3 under a `mismatches/` prefix. Uploads must be encrypted at rest, and credentials must not appear in logs.
