# Skill packs

Which skills to load into your AI coding tool before you start, by workflow. This is the "at setup" moment: everyone on the team starts with the same guardrails.

A skill is a written playbook the tool follows. Load the base pack once, then the pack for the work you are doing.

## Base pack: everyone, once per machine

| Skill | What it gives you | Install |
|---|---|---|
| `find-skills` | Finds an existing skill for a task before you improvise one | `npx skills add vercel-labs/skills --skill find-skills` |
| `ponytail` | Keeps changes small and makes the tool reuse existing code before writing new code | In Claude Code: `/plugin marketplace add DietrichGebert/ponytail`, then `/plugin install ponytail@ponytail` |

Then fill the engineering memory, once:

```
cd guardian
gh auth login
scripts/fetch-context.sh https://github.com/capitalone/locopy https://github.com/capitalone/datacompy
./bin/guardian doctor
```

On Windows, set `export GUARDIAN_PYTHON=/c/Python313/python` (or your own Python path) first.

## Workflow packs

These skills live in `guardian/.claude/skills/` and load on their own when you start `claude` from inside `guardian/`. Nothing to install.

| You are about to | Skills used | Command |
|---|---|---|
| Start a ticket | `blueprint`, which calls `reuse-check` and `pr-history` | `claude -p "/blueprint $(cat ticket.md)"` |
| Check your change before opening a PR | `pr-review` on a local diff | `git diff main > my.diff`, then `claude -p "/pr-review my.diff"` |
| Review an open PR | `pr-review`, which runs `reuse-check`, `pr-history`, `security-compliance` and `cost` | `claude -p "/pr-review <PR URL>"` |
| Ask one question | Any single track | `claude -p "/reuse-check <description>"` |

## Rules

- **Add a skill to a pack by editing this file in a pull request.** Nobody's tool changes silently.
- **Company rules go in `rules.md`, not in a skill**, so the security and cost tracks pick them up without edits.
- **Other tools:** the playbooks are plain Markdown. A tool that cannot load Claude Code skills can be pointed at the `SKILL.md` file directly.

## Known limit

`ponytail` adds a short "skipped / not checked" note to the end of console output. The review comment saved in `out/` is not affected.
