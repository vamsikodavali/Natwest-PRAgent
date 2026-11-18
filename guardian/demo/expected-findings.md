# Demo: expected results

The demo has two steps. Both use `demo/ticket.md` and the planted change in `tests/fixtures/planted.diff` (the same code is opened as the demo pull request).

## Step 1: blueprint for the ticket

```
claude -p "/blueprint $(cat demo/ticket.md)"
```

Must show, under "Reuse directly": `S3.upload_to_s3` in `locopy/locopy/s3.py`.

## Step 2: review of the planted change

```
claude -p "/pr-review <demo PR URL>"          # or: /pr-review tests/fixtures/planted.diff
```

Lines refer to `datacompy/export.py` in the planted change.

| # | Line | Track | Must cite | What was planted |
|---|---|---|---|---|
| 1 | 9, 10 | security | `SEC-01` | Hardcoded AWS access key and secret |
| 2 | 27 | security | `SEC-02` | Customer ID and email written to the log |
| 3 | 13 | reuse | `locopy/locopy/s3.py` | `upload_to_s3` re-implements locopy's S3 upload |
| 4 | 25 | cost | `COST-02` | `SELECT *` with no filter or limit |
| 5 | 29 | cost | `COST-03` | One S3 upload per row inside a loop |
| 6 | 34 | cost | `COST-01` | Warehouse resized to `X4LARGE` with no justification |

A run passes when all six appear, no secret value is printed, and nothing is cited that does not exist. Extra findings backed by a repo policy in `data/` (for example `datacompy:PRIV-003`, or locopy's rule that S3 uploads use server-side encryption) are welcome, not failures.
