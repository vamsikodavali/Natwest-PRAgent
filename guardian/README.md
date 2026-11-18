# guardian: reuse workflow (P2)

The **Before coding** step of OpenHands. A developer hands over a ticket and gets back one screen: the code that already does it, the past PRs that tried it (and why they were rejected), and the people to ask.

```bash
cd guardian
claude -p "/blueprint $(cat ticket.md)"          # verified blueprint, one screen
claude -p "/reuse-check <description or diff>"   # did we already build this?
claude -p "/pr-history  <description or diff>"   # was this tried or rejected before?
```

## How it works

```
 ticket / diff ─▶ bin/guardian (deterministic retrieval) ─▶ ranked candidates + evidence (JSON)
                                                              │
                         SKILL.md playbook (judgement) ◀──────┘
                         Claude reads each candidate's exact lines, drops false hits,
                         quotes real rejection reasons ─▶ one-screen blueprint
```

Retrieval and judgement are kept apart on purpose:

| Layer | Who does it | Why |
|---|---|---|
| Find candidates | `guardian_kit` (Python, stdlib only) | Same input gives the same output. It's fast (under 0.5s on three real repos), testable, and costs no tokens. |
| Confirm and explain | Claude, following `.claude/skills/*/SKILL.md` | It reads the code and decides whether it *really* covers the use case. Anything without evidence is dropped. |

### Reuse ranking (`reuse.py`)
- **Intent extraction:** the ticket is split into concepts, and each concept is grown with banking-aware synonyms (`mask ≈ redact ≈ obfuscate`, `iban ≈ bic ≈ sortcode`, `retry ≈ backoff`). For a diff, only the **added** lines are used, and names the diff defines count double.
- **Symbol index:** functions, methods and types across Python, JS/TS, Java, Kotlin, Go, Rust, Ruby, PHP, C#, shell, SQL and Terraform, together with their docstrings and doc comments.
- **Repo breakdown docs:** each repo's file/folder breakdown `.md` (`context/repos/<repo>.md`, or `STRUCTURE.md`, `ARCHITECTURE.md` and similar inside the repo) is parsed, and its plain-English descriptions are attached to the files and symbols they mention. This finds `amt_str()` from "formats money amounts as currency strings" even though the code has no docstring.
- **Scoring:** each concept counts once, through its strongest field (name 3.0, breakdown 2.2, doc 1.4, path 0.9), weighted by IDF, then multiplied by *coverage* (how much of the ticket the candidate touches). Tests, `docs/`, `scripts/` and private helpers are downweighted. Weaker hits in the same file collapse into one entry.
- **How to call it:** a real call site from the codebase where one exists, otherwise an import line.

### PR history (`history.py`)
- **Accepts any export shape:** `gh pr view --json`, GitHub REST, GitLab, Bitbucket and flat hand-written JSON. A file can hold one PR, a list, or a wrapper. Broken files become warnings; they never cause a crash.
- **Outcome:** `merged`, `rejected` (closed without merging) or `open`.
- **Rejection reason:** an explicit reason field if one exists. Otherwise the remark with the strongest decision signal: CHANGES_REQUESTED, or cue words like "duplicate", "instead" or "policy" from someone other than the author. Bot remarks are ignored.
- **Boost:** PRs that touched the reuse candidates' files are ranked up.

### Owners (`owners.py`)
- Git commits to the matched files, weighted by recency (one-year half-life), with bots removed.
- `CODEOWNERS`, using the last matching rule.
- PR authors and the reviewers who rejected similar work. Every person comes with an evidence string.

## Context contract (from P3)

```
context/
  repos/<name>/        git clone (history needed for owners; shallow --depth 300 is fine)
  repos/<name>.md      optional file/folder breakdown for <name>
  prs/**/*.json        PR exports; a sub-folder name is used as the repo when the JSON has none
```

Point elsewhere with `GUARDIAN_CONTEXT=/path` or `--context`. Run `./bin/guardian doctor` before a demo. It reports, for each repo, the files and symbols indexed, which breakdown doc was found, PR counts by outcome, and how many rejected PRs have a reason that can be found.

## CLI

```
bin/guardian reuse     [--limit N] [--repo R] [--include-tests] <text | - | --file F>
bin/guardian history   [--limit N] [--state merged|rejected|open] [--related-file P] <text>
bin/guardian owners    <repo>/<path> ...
bin/guardian blueprint [--limit N] [--pr-limit N] [--owner-limit N] <text>
bin/guardian doctor
        --format md|json   (skills use json)    exit 0 ok / 2 bad input or missing context
```

`bin/guardian` uses the `pr_agent` conda env if it exists and falls back to any `python3` 3.9 or later. There are no runtime dependencies.

## Develop

```bash
conda env create -f environment.yml     # or: make env
make check                              # ruff + 44 tests (CI runs Python 3.9 and 3.12)
make demo                               # builds a sample context with git history and runs a blueprint
```

The sample context (`tests/sample_context.py`) has two repos with dated commits by several authors, a breakdown doc, and PRs in three export formats plus a broken file. The test suite checks that every helper is found **from a plain-English description**, that an unrelated ticket returns nothing, and that the blueprint fits on one screen.
