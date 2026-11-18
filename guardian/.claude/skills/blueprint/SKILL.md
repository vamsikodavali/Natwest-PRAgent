---
name: blueprint
description: Turn a ticket into a one-screen build blueprint before any code is written. It lists existing code to reuse (verified), similar past pull requests with the reasons rejected ones were turned down, and who to ask (from git history and PRs). Use when a developer picks up a ticket or asks "what do I need to know before building X?".
argument-hint: <ticket text, or path to ticket.md>
allowed-tools: Bash(./bin/guardian:*), Read, Grep, Glob
---

# Blueprint

> **Reply format:** your final message is only the `## Blueprint` block defined at the end of this file. It starts with that heading, with no thinking-out-loud before it and no summary after it.

Ticket: $ARGUMENTS

Produce one screen that stops a developer rebuilding something that already exists.
Rule: *evidence or silence*. Every line cites a file path, a PR number or a git commit history. Anything you can't back up gets cut.

## 1. Gather (one command: reuse-check, pr-history and owners together)

If the ticket is a path to an existing file, use `--file <path>`; otherwise:

**Before running, write the search terms the ticket doesn't say (one line, no code lookup).** Developers describe *behaviour* ("make it unreadable", "funds land"), while code names *mechanisms* (`mask`, `settlement`). Bridge the gap in this format:

```
<ticket word>=<alt>,<alt>; <ticket word>=<alt>; <likely_function_name>, <likelyName>
```

- Link each alternative to the ticket word it replaces (`unreadable=mask,redact,obfuscate`). Linked terms count like the ticket's own words.
- Add 2 to 4 guesses at function or class names in the repo's style (`mask_account`, `maskPan`). An exact hit gets a strong bonus.
- 5 to 12 terms in total. Use domain language (`settlement`, `sort code`, `backoff`). Don't add generic words like `data`, `util` or `helper`.
- This step raised "right helper in top 3" from 62% to 88% on real repos (`make eval-public`), so don't skip it.

```bash
./bin/guardian blueprint --format json --expand '<your expansion line>' - <<'GUARDIAN_EOF'
<the ticket, verbatim>
GUARDIAN_EOF
```

The JSON has `reuse` (ranked code candidates, same fields as the reuse-check skill), `prs` (similar PRs, already boosted when they touched the candidate files), `owners` (ranked people: git commits to the matched files weighted by recency, CODEOWNERS, PR authors and rejecting reviewers, each with an `evidence` string), `stats` and `warnings`.

If the command fails, print its message and stop. `./bin/guardian doctor` diagnoses context problems.

## 2. Verify (this is where you add value over the engine)

1. **Reuse:** Read each of the top 4 candidates' `abs_path` from `line` to `end_line`. Don't search for the file: `abs_path` is correct even when the context folder is outside this directory. Then mark each one **covers** (does the job, maybe through a parameter), **partial: <gap in five words or fewer>**, or drop it (the name matched but the behaviour is different). Everything you need is in this file, so don't open the other skills.
2. **PRs:** drop PRs about something else. For a rejected PR with an empty `reason`, read its `source` JSON and quote the reviewer's real objection. Never paraphrase it into something stronger.
3. **Owners:** if you dropped a reuse candidate, drop people whose only evidence was that file. If no candidate survived but a PR did, its author and reviewer are still worth asking.

## 3. Output: your whole reply is this block (≤ 25 lines). Start with `## Blueprint`; no sentence before or after it

```
## Blueprint: <ticket title, ≤ 70 chars>

### Reuse directly
1. `name(params)` - repo/path:line - covers
   Call: `<real call site or import + call>`
2. `name(params)` - repo/path:line - partial: <gap>; extend it rather than writing a new one

### Reference PRs
- #142 rejected "title" - why (reviewer): "quoted reason"
- #101 merged "title" - added the helper above

### Who to ask
- Name <email>: <evidence, e.g. 2 commits to masking.py (last 2026-06-01); rejected #142>
```

- At most 3 reuse entries, 3 PRs and 3 people.
- An empty section gets one line: `- Nothing found in context/ (searched: <concepts>).` Never pad.
- If the ticket clearly needs new code alongside the reuse, add one final line: `Build new: <what's genuinely missing>`.
