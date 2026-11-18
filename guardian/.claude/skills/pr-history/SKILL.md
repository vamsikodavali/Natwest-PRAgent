---
name: pr-history
description: Search past pull requests in context/prs for similar work and report each one's number, outcome (merged or rejected) and, for rejected ones, the reviewer's reason. Use when asked "was this tried before?", when planning a ticket, or as the History track of a PR review.
argument-hint: <feature description | unified diff | path to a .diff/.md file>
allowed-tools: Bash(./bin/guardian:*), Read, Grep, Glob
---

# PR history

> **Reply format:** your final message is only the `### Reference PRs` block defined at the end of this file. It starts with that heading, with no thinking-out-loud before it and no summary after it.

Answer: **has this been tried before, and what happened?** Rejected PRs matter most, because their reasons are the institutional memory nobody remembers.
Rule: *evidence or silence*. Every line must cite a PR number that exists in `context/prs/`.

Input: $ARGUMENTS

## 1. Gather matches (deterministic)

**Before running, write the search terms the ticket doesn't say (one line, no code lookup).** Developers describe *behaviour* ("make it unreadable", "funds land"), while code names *mechanisms* (`mask`, `settlement`). Bridge the gap in this format:

```
<ticket word>=<alt>,<alt>; <ticket word>=<alt>; <likely_function_name>, <likelyName>
```

- Link each alternative to the ticket word it replaces (`unreadable=mask,redact,obfuscate`). Linked terms count like the ticket's own words.
- Add 2 to 4 guesses at function or class names in the repo's style (`mask_account`, `maskPan`). An exact hit gets a strong bonus.
- 5 to 12 terms in total. Use domain language (`settlement`, `sort code`, `backoff`). Don't add generic words like `data`, `util` or `helper`.
- This step raised "right helper in top 3" from 62% to 88% on real repos (`make eval-public`), so don't skip it.

```bash
./bin/guardian history --format json --limit 6 --expand '<your expansion line>' - <<'GUARDIAN_EOF'
<the input, verbatim>
GUARDIAN_EOF
```

If you already know which files the work touches (for example from a reuse check), add `--related-file <repo-relative path>` for each one. PRs that touched the same files get boosted.

Each match gives `number`, `title`, `state` (`merged` | `rejected` | `open`), `repo`, `reason`, `reason_by`, `shared_files`, `matched` and `source` (the JSON file it came from). PR exports in any common shape (gh CLI, GitHub REST, GitLab, flat) are normalised. Files that won't parse appear under `warnings`.

## 2. Confirm (judgement)

- Drop matches whose title and body are about something else, even if a word matched.
- For each **rejected** match: if `reason` is empty or unclear, Read its `source` file (an absolute path), find that PR, and pull the reviewer's actual objection from the reviews or comments. Quote it. Don't paraphrase it into something stronger. If no reason was ever written, say `no reason recorded`.
- For a **merged** match, say in a few words why it's relevant: it added the helper, or it touched the same file.

## 3. Output: your whole reply is this block. No sentence before or after it

```
### Reference PRs
- #142 rejected (repo) "PR title" - why (reviewer): "quoted reason"
- #101 merged (repo) "PR title" - added mask_account_number
```

- At most 4 entries. Rejected entries first, then merged, then open.
- If nothing is relevant: `- No similar past pull requests in <N> exported PRs.`
- No preamble, no closing summary, no scores.
