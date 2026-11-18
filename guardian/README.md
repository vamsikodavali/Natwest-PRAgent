# guardian: reuse workflow (P2)

The **Before coding** step of OpenHands. A developer hands over a ticket and gets back one screen: the code that already does it, the past PRs that tried it (and why they were rejected), and the people to ask.

> **New here?** See **[docs/RUN_AND_INTEGRATE.md](docs/RUN_AND_INTEGRATE.md)** for a 60-second demo, running with or without a model, plugging in your own repos, and calling it from `/pr-review` (JSON contract).

```bash
cd guardian
make demo                                        # no model needed: sample context, one blueprint
./bin/guardian blueprint "<ticket>"              # engine only, local, free
claude -p "/blueprint $(cat ticket.md)"          # verified blueprint, one screen
claude -p "/reuse-check <description or diff>"   # did we already build this?
claude -p "/pr-history  <description or diff>"   # was this tried or rejected before?
```

## How it works

```
 ticket ─▶ ① Claude: what would the code be called?  ("funds land" → settlement, business day, bank holiday)
              │  --expand
              ▼
           ② bin/guardian: deterministic retrieval   (symbols, breakdown docs, PRs, git owners → ranked JSON)
              │
              ▼
           ③ Claude: open each candidate's exact lines, drop false hits, quote real rejection reasons
              │
              ▼
           one-screen blueprint, every line backed by a file, a PR number or git history
```

The model handles the language at both ends; the engine handles the search in the middle:

| Step | Who | Why |
|---|---|---|
| ① Expand the query | Claude | Tickets describe *behaviour*; code names *mechanisms*. A model bridges that better than any synonym list. |
| ② Retrieve | `guardian_kit` (Python, stdlib only) | Same input gives the same output. Under 0.5s on three real repos, testable, costs no tokens, and runs entirely on your machine. |
| ③ Verify | Claude | Reads the code and decides whether it *really* covers the use case. Anything without evidence is dropped. |

## Measured, not claimed

`guardian eval` runs labelled tickets (each with a known answer, or with none) and reports how often the right helper comes back:

| Retrieval quality | Public repos¹: engine alone | Public repos¹: with ① | Sample context: engine alone | Sample context: with ① |
|---|---|---|---|---|
| right helper in top 3 | 62% | **88%** | 83% | **100%** |
| right helper ranked 1st | 38% | 71% | 75% | 83% |
| silent when nothing exists | 75% | 75% | 100% | 100% |

¹ 24 tickets on requests, axios and spring-petclinic at pinned commits. I didn't write that code, and the tickets avoid the function names. Reproduce with `make eval-public`. The expansions in the case files simulate step ①. In live runs Claude writes its own, for example finding `add_business_days` from "when will funds land if sent the Friday before Christmas?", where the engine alone finds nothing.

CI fails if top-3 recall on the sample set drops below 75%. When P1 reports a miss, add it as a case first, then fix it.

### Reuse ranking (`reuse.py`)
- **Intent extraction:** the ticket is split into concepts, and each concept is grown with banking-aware synonyms (`mask ≈ redact ≈ obfuscate`, `iban ≈ bic ≈ sortcode`, `retry ≈ backoff`). For a diff, only the **added** lines are used, and names the diff defines count double.
- **Symbol index:** functions, methods and types across Python, JS/TS, Java, Kotlin, Go, Rust, Ruby, PHP, C#, shell, SQL and Terraform, together with their docstrings and doc comments. This includes Java interface and abstract methods such as Spring Data finders.
- **Repo breakdown docs:** each repo's file/folder breakdown `.md` (`context/repos/<repo>.md`, or `STRUCTURE.md`, `ARCHITECTURE.md` and similar inside the repo) is parsed, and its plain-English descriptions are attached to the files and symbols they mention. This finds `amt_str()` from "formats money amounts as currency strings" even though the code has no docstring.
- **Scoring:** each concept counts once, through its strongest field (name 3.0, breakdown 2.2, doc 1.4, path 0.9), weighted by IDF, then multiplied by:
  - *coverage*: how much of the ticket the candidate touches;
  - *name precision*: how much of its name the ticket explains, so `PetValidator` for "validate a pet" beats a class that only matches through a long docstring.

  Ticket words that appear nowhere in the code don't count against any candidate. Tests, `docs/`, `scripts/` and private helpers are downweighted. Weaker same-file hits fold into one entry, but strong ones in grab-bag `utils` files keep their own.
- **Query expansion (`--expand`):** `unreadable=mask,redact; maskPan`. Linked terms count as the ticket's own words, and guessed identifiers get an exact-name bonus. Unlinked terms add score but never reduce coverage.
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
bin/guardian reuse     [--expand SPEC] [--limit N] [--repo R] [--include-tests] <text | - | --file F>
bin/guardian history   [--expand SPEC] [--limit N] [--state merged|rejected|open] [--related-file P] <text>
bin/guardian owners    <repo>/<path> ...
bin/guardian blueprint [--expand SPEC] [--limit N] [--pr-limit N] [--owner-limit N] <text>
bin/guardian eval      <cases.json> [--mode both|baseline|expanded] [--min-recall 0.75]
bin/guardian doctor
        --format md|json   (skills use json)
        exit 0 ok / 1 eval below --min-recall / 2 bad input or missing context
```

`bin/guardian` uses the `pr_agent` conda env if it exists and falls back to any `python3` 3.9 or later. There are no runtime dependencies.

## Develop

```bash
conda env create -f environment.yml     # or: make env
make check                              # ruff + 53 tests (CI runs Python 3.9 and 3.12)
make demo                               # builds a sample context with git history and runs a blueprint
make eval                               # retrieval quality on the sample set (CI gate)
make eval-public                        # clones pinned public repos, reports the numbers above
```

The sample context (`tests/sample_context.py`) has two repos with dated commits by several authors, a breakdown doc, and PRs in three export formats plus a broken file. The test suite checks that every helper is found **from a plain-English description**, that an unrelated ticket returns nothing, and that the blueprint fits on one screen.
