"""Turn raw GitHub API responses into the PR export that context/prs/ expects.

Used by scripts/fetch-context.sh so the script needs nothing beyond git, curl
and the Python that already runs bin/guardian (no Node.js, works on Windows).

REST path (no `gh`): pulls + inline review comments + conversation comments.
Conversation comments matter most: "closing because we already have X" is
usually written there, not on a line of code.
"""

from __future__ import annotations

import json
from pathlib import Path


class ImportErrorMessage(RuntimeError):
    """GitHub returned something other than a list (rate limit, 404, auth)."""


def _load_list(path: Path, what: str) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    msg = data.get("message") if isinstance(data, dict) else None
    raise ImportErrorMessage(f"GitHub API error ({what}): {msg or 'unexpected response'}")


def _login(user) -> str:
    return (user or {}).get("login") or "" if isinstance(user, dict) else ""


def from_rest(pulls: Path, review_comments: Path, issue_comments: list[Path]) -> list[dict]:
    prs = _load_list(pulls, "pulls")
    inline = _load_list(review_comments, "review comments")
    convo: list = []
    for p in issue_comments:
        convo.extend(_load_list(p, "issue comments"))

    by_url: dict[str, list] = {}
    for c in inline:
        by_url.setdefault(c.get("pull_request_url", ""), []).append(
            {"author": {"login": _login(c.get("user"))}, "body": c.get("body") or "", "path": c.get("path"),
             "createdAt": c.get("created_at")})
    by_number: dict[int, list] = {}
    for c in convo:
        try:
            n = int(str(c.get("issue_url", "")).rstrip("/").rsplit("/", 1)[-1])
        except ValueError:
            continue
        by_number.setdefault(n, []).append(
            {"author": {"login": _login(c.get("user"))}, "body": c.get("body") or "", "createdAt": c.get("created_at")})

    out = []
    for p in prs:
        comments = by_url.get(p.get("url", ""), []) + by_number.get(p.get("number"), [])
        comments.sort(key=lambda c: c.get("createdAt") or "")
        out.append({
            "number": p.get("number"),
            "title": p.get("title"),
            "body": p.get("body"),
            "state": "MERGED" if p.get("merged_at") else ("OPEN" if p.get("state") == "open" else "CLOSED"),
            "author": {"login": _login(p.get("user"))},
            "mergedAt": p.get("merged_at"),
            "closedAt": p.get("closed_at"),
            "comments": comments,
            "files": [],
            "reviews": [],
            "url": p.get("html_url"),
        })
    return out


def from_gh(path: Path) -> list[dict]:
    """`gh pr list --json ...` output is already in the right shape; just validate it."""
    return _load_list(path, "gh pr list")


def write(prs: list[dict], out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(prs, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)  # never leave a half-written export behind
    return len(prs)
