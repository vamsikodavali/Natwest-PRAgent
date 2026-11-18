# Running and integrating the reuse workflow

For: anyone on the team who needs to run the blueprint, plug their own repos in, or call reuse and history from another skill (for example `/pr-review`).

---

## 1. Run it in 60 seconds

```bash
git checkout p2/reuse-workflow
cd guardian
make demo            # builds a sample context and prints a blueprint. No model, no setup.
```

You should see `mask_account_number` under **Reuse directly**, PR #142 under **Reference PRs** with the reviewer's reason, and Asha Rao under **Who to ask**.

---

## 2. Two ways to run

| | Engine only | Full skill (verified by Claude) |
|---|---|---|
| Command | `./bin/guardian blueprint "<ticket>"` | `claude -p "/blueprint $(cat ticket.md)"` |
| Needs a model? | **No.** Plain Python, nothing to install | Yes. Claude Code, logged in |
| Sends code anywhere? | No, it runs entirely on your machine | Yes. Claude reads the matched code |
| What it does | Ranks candidates, PRs and owners | Also opens each candidate, drops false matches, quotes the real rejection reasons |
| Time and cost | Under 1 second, free | About 20 seconds, about $0.20 per ticket (measured on Opus and Sonnet) |

**Always run `claude` from inside `guardian/`.** That's where the skills live (`guardian/.claude/skills/`).

### Commands

```bash
# engine only
./bin/guardian doctor                                  # is context/ ready?
./bin/guardian blueprint "Mask account numbers before logging"
./bin/guardian blueprint --file ticket.md
./bin/guardian reuse   "retry failed gateway calls"    # did we already build this?
./bin/guardian history "retry failed gateway calls"    # was it tried or rejected before?
./bin/guardian owners  payments-core/src/payments_core/utils/masking.py
git diff main | ./bin/guardian reuse -                 # a diff works as input too

# full skills
claude -p "/blueprint $(cat ticket.md)"
claude -p "/reuse-check <description or diff>"
claude -p "/pr-history <description or diff>"
claude -p --model claude-sonnet-5-5 "/blueprint $(cat ticket.md)"   # pick a model
```

Every command accepts `--format json` (that's what the skills use) and `--context <dir>`.
Exit codes: `0` means OK, including "nothing found". `2` means bad input or a missing context folder.

### Model and authentication

The code contains no API key. `claude -p` uses whatever Claude Code is logged in with: your Claude plan, or `ANTHROPIC_API_KEY` if that's set in your shell. Check which with `/status` inside `claude`.
Use the full model ID with `--model`. The bare alias `sonnet` resolved to an older model this account can't use.

---

## 3. Point it at your own repos

The engine reads one folder, the **context**:

```
context/
  repos/<name>/          git clone of each repo (history is needed for "Who to ask")
  repos/<name>.md        optional: file/folder breakdown of <name>; improves matching a lot
  prs/<name>/*.json      optional: exported pull requests
```

By default this is `guardian/context/`. To use another folder, `export GUARDIAN_CONTEXT=/path/to/context`.

```bash
cd guardian
mkdir -p context/repos context/prs
ln -s ~/code/payments-service context/repos/payments-service       # link a repo you already have, or:
git clone --depth 300 <url> context/repos/other-repo               # 300 commits is enough for owners

gh pr list --repo org/payments-service --state all --limit 200 \
  --json number,title,body,state,author,mergedAt,files,reviews,comments,url \
  > context/prs/payments-service/prs.json                          # review comments give rejection reasons

./bin/guardian doctor
```

`doctor` reports, for each repo: files and functions indexed, which breakdown doc it found, how many paths that doc describes, PR counts by outcome, and how many rejected PRs have a findable reason. Fix anything it flags before a demo.

**Breakdown doc format.** Any Markdown that names real paths works: a table, a list, a tree or headings.

```markdown
| `src/payments_core/utils/masking.py` | Masks account numbers, card PANs and emails so PII never reaches logs |
| `src/payments_core/utils/`           | Shared helpers used by every service |
```

Text under a heading that names a folder applies to everything in that folder. A backticked function name, such as `` `amt_str` ``, attaches the line to that function.

**PR export format.** It accepts `gh pr list/view --json`, GitHub REST, GitLab, Bitbucket, or flat JSON. Each file can hold one PR, a list, or a wrapper (`{"pull_requests": [...]}`). A minimal record:

```json
{"number": 142, "title": "New PII redactor", "state": "closed", "merged": false,
 "files": ["src/x.py"], "rejection_reason": "Duplicates mask_account_number; reuse it."}
```

`merged`/`mergedAt` gives merged. Closed without a merge gives rejected. Everything else is open. If there's no explicit reason field, the reason is taken from review or comment text: change requests and comments from people other than the author, with words like "duplicate", "instead" or "policy". Bot PRs (Dependabot and similar) are ignored. Broken files appear as warnings in `doctor`.

> **Data handling:** the engine runs entirely on your machine. The `claude -p` skills send matched code to the model. Internal NatWest repos need security and legal sign-off first.

---

## 4. Integrate from another skill (for example `/pr-review`)

Don't build another search. Call the engine and use its JSON. The Reuse and History tracks of a PR review are these two calls:

```bash
gh pr diff <PR> > /tmp/pr.diff
./bin/guardian reuse   --format json --file /tmp/pr.diff
./bin/guardian history --format json --file /tmp/pr.diff --related-file <path touched by the PR> ...
```

When the input is a diff, the engine uses only the **added** lines and treats function names defined in the diff as strong signals. Files the diff itself touches are downweighted, so it won't suggest "reuse the code you're editing".

In your skill's frontmatter:

```yaml
allowed-tools: Bash(./bin/guardian:*), Read, Grep, Glob
```

Then follow the verification steps in `.claude/skills/reuse-check/SKILL.md`: Read each candidate's `abs_path` from `line` to `end_line`, then keep or drop it. Every finding you post must cite `repo/path:line` or `#PR`.

### JSON contract (stable fields)

`reuse --format json` returns `{"query": [...concepts], "candidates": [...], "stats": {...}}`. Each candidate:

| field | meaning |
|---|---|
| `name`, `kind`, `parent` | symbol, `function` / `method` / `type`, enclosing class |
| `repo`, `path`, `line`, `end_line` | where it is (`path` is relative to the repo) |
| `abs_path` | absolute file path. **Always Read this one** |
| `signature`, `doc` | definition line and docstring or doc comment |
| `map_note` | what the repo breakdown doc says about it |
| `call_sites` | up to 2 real usages, `path:line  code` |
| `import_hint` | import line, when there are no call sites |
| `also_in_file` | weaker matches in the same file |
| `score`, `coverage`, `confidence`, `matched` | ranking diagnostics (don't show these to users) |

`history --format json` returns `{"prs": [...], "prs_loaded": N, "warnings": [...]}`. Each PR:

| field | meaning |
|---|---|
| `number`, `title`, `state`, `repo`, `url` | `state` is `merged`, `rejected` or `open` |
| `reason`, `reason_by` | the reviewer's objection (quote it) and who wrote it |
| `shared_files` | files this PR touched that are also in `--related-file` |
| `author`, `reviewers`, `files`, `date`, `source` | `source` is the absolute path of the JSON file |

`blueprint --format json` returns `{"reuse": [...], "prs": [...], "owners": [...], "stats": {...}, "warnings": [...]}`. Each owner has `name`, `email`, `commits`, `last_commit`, `codeowner_for`, `pr_roles` and a ready-to-print `evidence` string.

### From Python

```python
import sys; sys.path.insert(0, "guardian/lib")        # or: pip install -e guardian
from pathlib import Path
from guardian_kit.text import build_query
from guardian_kit.blueprint import run_blueprint

bp = run_blueprint(Path("guardian/context"), build_query(ticket_text))
bp["reuse"][0]["abs_path"], bp["prs"][0]["reason"], bp["owners"][0]["evidence"]
```

---

## 5. Develop and test

```bash
conda env create -f environment.yml    # pr_agent env: Python 3.12 plus pytest and ruff (dev only)
make check                             # ruff + 45 tests
make demo
```

CI (`.github/workflows/guardian.yml`) runs lint, the tests on Python 3.9 and 3.12, and a command-line smoke test on every PR that touches `guardian/`.

| Tuning knob | Where | Effect |
|---|---|---|
| Synonym groups | `text.py: _SYNONYM_GROUPS` | Add domain words, e.g. `("chaps", "bacs", "fps")` |
| Ticket filler words | `text.py: TICKET_FILLER` | Words that should never count as intent |
| Field weights and cutoffs | `reuse.py` top of file | Name, breakdown doc, doc comment and path weights; noise floor |
| Rejection cue words | `history.py: REASON_CUES` | What counts as a reviewer's reason |

When P1 reports a miss, reproduce it with `./bin/guardian reuse --format json "<their wording>"`. Check `query` (the concepts it extracted) and `matched`. Usually the fix is a synonym or a breakdown-doc line, and the scoring doesn't need to change.
