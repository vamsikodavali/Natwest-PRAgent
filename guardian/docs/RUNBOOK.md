# Runbook: set up, run, and demo OpenHands

For: anyone on the team running the system or presenting the demo. Every command runs from the `guardian/` folder.

---

## 1. One-time setup (about 5 minutes)

| Need | Why | Install / check |
|---|---|---|
| Claude Code, logged in | Runs the skills (`claude -p "/blueprint ..."`) | `claude`, then `/status` |
| git, curl | Fetch repos and PRs | Already on macOS and Linux |
| Python 3.9 or later | The search engine (`bin/guardian`). Standard library only | `conda env create -f environment.yml` (env `pr_agent`), or any `python3` |
| `gh`, logged in (**optional**) | Lets `/pr-review` post its review on the GitHub PR. Without it, the review is written to `out/` only | `brew install gh`, then `gh auth login` |

Fetch the 7 repos the policy documents in `data/` describe (about 90 seconds):

```bash
cd guardian
scripts/fetch-context.sh \
  https://github.com/capitalone/locopy https://github.com/capitalone/datacompy \
  https://github.com/capitalone/DataProfiler https://github.com/capitalone/rubicon-ml \
  https://github.com/ing-bank/probatus https://github.com/ing-bank/popmon https://github.com/ing-bank/skorecard
./bin/guardian doctor
```

`doctor` should list 7 repos, each with a `*_technical_policy.md` breakdown from `data/`, and about 660 PRs. Anonymous GitHub access allows 60 API calls an hour and each repo uses 4. If you hit the limit, `export GITHUB_TOKEN=<a read-only token>` first.

---

## 2. Run the demo (about 3 minutes)

The demo story: a ticket asks for something that already exists, and then a pull request ignores it and adds a hardcoded credential, customer data in logs and costly infrastructure.

**Step 1: before coding, the blueprint** (about 30 seconds)

```bash
claude -p "/blueprint $(cat demo/ticket.md)"
```

Expect under **Reuse directly**: `S3.upload_to_s3` in `locopy/locopy/s3.py`, which already forces encryption. Also a related past PR (#399, credential redaction) and who to ask (git history and CODEOWNERS).

**Step 2: the pull request review** (about 50 seconds)

```bash
claude -p "/pr-review tests/fixtures/planted.diff"
```

Expect the `OPENHANDS ALERT` banner with 3 blockers, and `out/review-local-planted.md` containing 7 findings:

| Severity | Finding | Evidence |
|---|---|---|
| BLOCKER | Hardcoded AWS access key and secret (2 lines) | `SEC-01`, `datacompy:SEC-001` |
| BLOCKER | Customer ID and email written to logs | `SEC-02`, `datacompy:PRIV-003` |
| WARN | `upload_to_s3` re-implements locopy's encrypted upload | `locopy/locopy/s3.py:183` |
| WARN | `SELECT *` with no filter, per-row S3 upload, warehouse resized to X4LARGE | `COST-02`, `COST-03`, `COST-01` |

The full pass criteria are in [demo/expected-findings.md](../demo/expected-findings.md).

**Step 3: the same thing on GitHub, accepted vs blocked**

Two demo pull requests implement the same ticket:

| Branch | What it does | Expected verdict |
|---|---|---|
| `demo/accepted-mismatch-export` | Reuses `S3.upload_to_s3` with KMS, no secrets, logs counts only, bounded query | ✅ "no issues found" (verified locally: 0 findings, 32 s, $0.39) |
| `demo/blocked-mismatch-export` | The planted change | 3 blockers, 4 warnings |

```bash
claude -p "/pr-review https://github.com/vamsikodavali/Natwest-PRAgent/pull/<N>"
```

With `gh` logged in, the review is posted as a comment on the PR. Open both PRs side by side.

---

## 3. Everyday commands

```bash
claude -p "/reuse-check <feature description, or path to a .diff>"   # did we already build this?
claude -p "/pr-history <feature description>"                        # was it tried or rejected before?
./bin/guardian blueprint "<ticket>"        # engine only: no model, free, under 1 second
make test                                  # 67 tests
make eval-all                              # retrieval quality across all 7 repos (41 labelled tickets)
```

Use `--model claude-sonnet-5-5` (the full ID) to choose a model. The bare alias `sonnet` resolved to an older model on our accounts.

---

## 4. End-to-end test results (18 Nov 2026, Sonnet 5.5, all 7 repos)

| Test | Result | Time / cost |
|---|---|---|
| `fetch-context.sh`, 7 repos, no Node.js or `gh` | 7 repos, 661 PRs; 47 of 126 rejected PRs have a findable reason | 90 s |
| Demo step 1: `/blueprint demo/ticket.md` | ✅ names `S3.upload_to_s3` | 34 s, $0.28 |
| Demo step 2: `/pr-review planted.diff` | ✅ all 6 expected findings, 0 permission denials, file written | 50 s, $0.43 |
| `/blueprint`, locopy gzip + KMS upload | ✅ `compress_file_list` and `upload_to_s3`; caught the silent AES256 fallback | 24 s, $0.19 |
| `/blueprint`, credit-model drift (cross-repo) | ✅ `psi` (skorecard), popmon comparisons, probatus resemblance model; warned about open popmon bug #299 | 53 s, $0.35 |
| `/blueprint`, Vault password rotation (nothing exists) | ✅ "Build new", unrelated PRs dropped | 27 s, $0.18 |
| `/reuse-check` on a diff that hand-rolls `slugify` | ✅ points to rubicon-ml `slugify` with 2 real call sites | 22 s, $0.18 |
| `/pr-history`, datacompy CLI | ✅ rejected #534 with reviewer comments; merged #544 means extend the existing CLI | 29 s, $0.21 |
| Retrieval quality, 41 labelled tickets, 7 repos | right helper in top 3: 89%, top 5: 97% (with the model's search terms) | 1.4 s |

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Unknown skill` or skills not found | `claude` started outside `guardian/` | `cd guardian` first |
| "requires approval" / permission denied in a skill | A skill is missing its `allowed-tools` line | All 6 skills declare them now; pull `main` |
| `GitHub API error (pulls): API rate limit exceeded` | Over 60 anonymous calls in an hour | `export GITHUB_TOKEN=...`, or wait for the reset |
| Review written but not posted | `gh` not logged in | `gh auth login`, then re-run `/pr-review <url>` |
| "There's an issue with the selected model" | Short model alias | Use `--model claude-sonnet-5-5` |
| Empty "Who to ask" | Repo copied without its `.git` folder | Re-fetch with `scripts/fetch-context.sh` |
