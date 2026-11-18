"""Orchestration and one-screen rendering for reuse, history, owners and blueprint."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import history, owners, reuse
from .context import list_repos
from .text import Query

MAX_LINE = 120


def _clip(s: str, n: int = MAX_LINE) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _summary(c: reuse.Candidate) -> str:
    s = c.symbol
    return s.doc or s.map_note or ""


# ---------------------------------------------------------------- engines

def run_reuse(context: Path, query: Query, limit: int, repos=None, include_tests=False):
    return reuse.search(context, query, limit=limit, repos=repos, include_tests=include_tests)


def run_history(context: Path, query: Query, limit: int, related_files=None, state=None):
    prs, warnings = history.load_prs(context)
    return history.search(prs, query, limit=limit, related_files=related_files, state=state), warnings, len(prs)


def run_blueprint(context: Path, query: Query, reuse_limit=4, pr_limit=4, owner_limit=3, repos=None,
                  today: dt.date | None = None) -> dict:
    candidates, stats = run_reuse(context, query, reuse_limit, repos=repos)
    related = [c.symbol.path for c in candidates]
    matches, warnings, pr_count = run_history(context, query, pr_limit, related_files=related)
    repo_objs = {r.name: r for r in list_repos(context, repos)}
    owner_files = [(c.symbol.repo, c.symbol.path) for c in candidates[:3]]
    found, notes = owners.find_owners(repo_objs, owner_files, today=today)
    owners.add_pr_people(found, matches)
    ranked = owners.rank(found, owner_limit)
    return {
        "query": {"concepts": stats["query_concepts"], "is_diff": query.is_diff},
        "reuse": [c.to_dict() for c in candidates],
        "prs": [m.to_dict() for m in matches],
        "owners": [o.to_dict() for o in ranked],
        "stats": {**stats, "prs_loaded": pr_count},
        "warnings": warnings + notes,
    }


# ---------------------------------------------------------------- rendering

def render_reuse(cands: list[dict]) -> list[str]:
    if not cands:
        return ["- Nothing in context/repos covers this. Build it, and say so in the PR."]
    lines = []
    for i, c in enumerate(cands, 1):
        name = f"{c['parent']}.{c['name']}" if c["kind"] == "method" and c["parent"] else c["name"]
        lines.append(f"{i}. `{name}` - {c['repo']}/{c['path']}:{c['line']}")
        what = c.get("verdict") or c["doc"] or c["map_note"]
        if what:
            lines.append(f"   {_clip(what, MAX_LINE - 3)}")
        if c["call_sites"]:
            lines.append(f"   used at {_clip(c['call_sites'][0], MAX_LINE - 11)}")
        elif c["import_hint"]:
            lines.append(f"   {_clip(c['import_hint'], MAX_LINE - 3)}")
        if c.get("also_in_file"):
            lines.append("   same file: " + ", ".join(f"`{s}`" for s in c["also_in_file"]))
    return lines


def render_prs(prs: list[dict]) -> list[str]:
    if not prs:
        return ["- No similar past pull requests."]
    lines = []
    for p in prs:
        where = f" ({p['repo']})" if p["repo"] else ""
        lines.append(f"- #{p['number']} {p['state'].upper()}{where}: {_clip(p['title'], 70)}")
        if p["reason"]:
            by = f"{p['reason_by']}: " if p["reason_by"] else ""
            lines.append(f"  why: {by}\"{_clip(p['reason'], 220)}\"")
    return lines


def render_owners(people: list[dict]) -> list[str]:
    if not people:
        return ["- No owners found (no git history or CODEOWNERS for the matched files)."]
    out = []
    for o in people:
        who = o["name"] + (f" <{o['email']}>" if o["email"] and o["email"] != o["name"] else "")
        out.append(f"- {who}: {_clip(o['evidence'], 140 - len(who))}")
    return out


def render_blueprint(bp: dict, title: str = "") -> str:
    head = f"## Blueprint: {_clip(title, 70)}" if title else "## Blueprint"
    lines = [head, "", "### Reuse directly", *render_reuse(bp["reuse"]),
             "", "### Reference PRs", *render_prs(bp["prs"]),
             "", "### Who to ask", *render_owners(bp["owners"])]
    return "\n".join(lines)


def ticket_title(text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s
    return ""
