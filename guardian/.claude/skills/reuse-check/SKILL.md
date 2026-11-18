---
name: reuse-check
description: Find existing code in context/repos that already does what a feature description or diff needs, confirm it really covers the use case, and say exactly how to call it. Use when asked "did we already build this?", before writing a new helper, or as the Reuse track of a PR review.
argument-hint: <feature description | unified diff | path to a .diff/.md file>
allowed-tools: Bash(./bin/guardian:*), Read, Grep, Glob
---

# Reuse check

> **Reply format:** your final message is only the `### Reuse` block defined at the end of this file. It starts with that heading, with no thinking-out-loud before it and no summary after it.

Answer one question: **does something in `context/repos/` already do this?**
Rule: *evidence or silence*. Only report code you have opened and read. Never guess a path or a signature.

Input: $ARGUMENTS

## 1. Gather candidates (deterministic)

Run from the guardian folder. If the input is a path to an existing file, use `--file <path>`. Otherwise pass it on stdin so quotes and diffs survive:

**Before running, write the search terms the ticket doesn't say (one line, no code lookup).** Developers describe *behaviour* ("make it unreadable", "funds land"), while code names *mechanisms* (`mask`, `settlement`). Bridge the gap in this format:

```
<ticket word>=<alt>,<alt>; <ticket word>=<alt>; <likely_function_name>, <likelyName>
```

- Link each alternative to the ticket word it replaces (`unreadable=mask,redact,obfuscate`). Linked terms count like the ticket's own words.
- Add 2 to 4 guesses at function or class names in the repo's style (`mask_account`, `maskPan`). An exact hit gets a strong bonus.
- 5 to 12 terms in total. Use domain language (`settlement`, `sort code`, `backoff`). Don't add generic words like `data`, `util` or `helper`.
- This step raised "right helper in top 3" from 62% to 88% on real repos (`make eval-public`), so don't skip it.

```bash
./bin/guardian reuse --format json --limit 8 --expand '<your expansion line>' - <<'GUARDIAN_EOF'
<the input, verbatim>
GUARDIAN_EOF
```

The engine extracts intent words and their synonyms (for example mask/redact/obfuscate), searches every repo's functions, doc comments, file paths and the repo's file/folder breakdown `.md`, and returns ranked candidates. Each comes with `abs_path`, `location`, `line` to `end_line`, `signature`, `doc`, `map_note` (what the breakdown doc says about the file), `call_sites` (real usages) and `import_hint`.

If it exits non-zero, show its stderr message and stop. Usually that means `context/` is missing; `./bin/guardian doctor` explains.

## 2. Confirm each candidate (judgement)

For up to the top 5 candidates, **Read** the candidate's `abs_path` (always use it: the context folder may live outside this directory), from `line` to `end_line`, then decide:

- **covers**: it does what is asked, possibly through a parameter (for example `visible=4`).
- **partial**: it is the right place, but something specific is missing. Name the gap in five words or fewer ("no EUR support", "sync only").
- **drop**: the name matched but the behaviour is different. Remove it silently.

When the input is a diff, compare against what the diff **adds**. A candidate that the new code reimplements is the headline finding.

## 3. Fallback, only if nothing survived

Run one Grep over `context/repos` (`output_mode: files_with_matches`, `-i`) for the two or three strongest intent words or synonyms that the engine did not try. Read the best one or two hits and apply step 2 to them. If nothing survives, report "nothing found". That's a valid result.

## 4. Output: your whole reply is this block. No sentence before or after it

```
### Reuse
1. `name(params)` - repo/path:line - covers
   Does: <one line, in your words, from reading the code>
   Call: `<copy of a real call site, or the import line + a call>` (path:line of the call site if one exists)
2. `name(params)` - repo/path:line - partial: <gap>
   ...
```

- At most 3 entries, best first. Same-file siblings that also fit go on one line: `Also: name2, name3`.
- If nothing is confirmed: `### Reuse` then `- No existing implementation in <N> repos (searched: <concepts>).`
- No preamble, no closing summary, no scores.
