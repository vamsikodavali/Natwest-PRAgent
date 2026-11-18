# Rules

Starter set. Every security or cost finding must cite one of these IDs. Add rules here, never inside a skill.

## Security and compliance

| ID | Rule | Default severity |
|---|---|---|
| SEC-01 | No hardcoded secrets: API keys, passwords, tokens, private keys, or connection strings containing credentials. | BLOCKER |
| SEC-02 | No personal or customer identifiers (name, email, phone, account or customer ID, national ID) written to logs, prints or exception messages. | BLOCKER |
| SEC-03 | No credentials or full connection strings written to logs, prints or exception messages. | BLOCKER |
| SEC-04 | Changes to authentication, authorisation, or credential handling must be called out for explicit reviewer sign-off. | WARN |
| SEC-05 | No disabled TLS or certificate verification, and no plaintext transport for credentials or customer data. | BLOCKER |

## Cost

| ID | Rule | Default severity |
|---|---|---|
| COST-01 | Increases to compute, instance, cluster or warehouse size, or to replica and node counts, need a stated justification. | WARN |
| COST-02 | No unbounded warehouse or database queries: `SELECT *` or a full-table read with no `WHERE` or `LIMIT`. | WARN |
| COST-03 | No calls to paid APIs, warehouses or object storage inside a loop without batching or an upper bound. | WARN |
