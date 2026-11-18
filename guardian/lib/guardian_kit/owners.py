"""Who to ask: owners of the matched files, from CODEOWNERS and git history.

Ranking is commits weighted by recency (half-life one year), so the person who
wrote the helper last spring outranks someone who renamed it in 2017.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .context import Repo

HALF_LIFE_DAYS = 365.0
GIT_TIMEOUT_S = 15
BOT = re.compile(r"(\[bot\]|-bot\b|dependabot|renovate|github-actions|noreply@github\.com$|^bot@|-bot@|jenkins|ci@)", re.I)


@dataclass
class Owner:
    name: str
    email: str
    weight: float = 0.0
    commits: int = 0
    last: str = ""
    files: dict[str, int] = field(default_factory=dict)
    codeowner_for: list[str] = field(default_factory=list)
    pr_roles: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return (self.email or self.name).lower()

    def evidence(self) -> str:
        bits: list[str] = []
        if self.files:
            top = sorted(self.files.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
            files = ", ".join(Path(f).name for f, _ in top)
            bits.append(f"{self.commits} commit{'s' if self.commits != 1 else ''} to {files} (last {self.last})")
        if self.codeowner_for:
            bits.append("CODEOWNER of " + ", ".join(sorted(set(self.codeowner_for))[:2]))
        bits.extend(self.pr_roles[:2])
        return "; ".join(bits)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "commits": self.commits,
            "last_commit": self.last,
            "files": self.files,
            "codeowner_for": sorted(set(self.codeowner_for)),
            "pr_roles": self.pr_roles,
            "evidence": self.evidence(),
            "weight": round(self.weight, 2),
        }


def _git_log(repo: Path, relpath: str, max_commits: int = 200) -> list[tuple[str, str, str]]:
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "log", "--no-merges", "--follow", f"-n{max_commits}",
             "--format=%an%x1f%ae%x1f%as", "--", relpath],
            capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if res.returncode != 0:
        return []
    out = []
    for line in res.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            out.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


def _codeowners(repo: Path) -> list[tuple[str, list[str]]]:
    for rel in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS"):
        f = repo / rel
        if f.is_file():
            rules = []
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if not line or line.startswith("["):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    rules.append((parts[0], parts[1:]))
            return rules
    return []


def _codeowner_match(pattern: str, relpath: str) -> bool:
    p = pattern
    anchored = p.startswith("/")
    p = p.lstrip("/")
    if p.endswith("/"):
        p += "**"
    if "/" not in p.rstrip("*").rstrip("/") and not anchored:
        # bare name or glob matches at any depth
        return any(fnmatch.fnmatch(seg, p) for seg in relpath.split("/")) or fnmatch.fnmatch(relpath, "*/" + p)
    rx = re.escape(p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return re.match(rf"^{rx}(/.*)?$", relpath) is not None


def find_owners(
    repos: dict[str, Repo],
    files: list[tuple[str, str]],
    today: dt.date | None = None,
) -> tuple[dict[str, Owner], list[str]]:
    """``files`` is a list of (repo name, repo-relative path)."""
    today = today or dt.date.today()
    owners: dict[str, Owner] = {}
    notes: list[str] = []
    seen_files: set[tuple[str, str]] = set()
    for repo_name, rel in files:
        if (repo_name, rel) in seen_files:
            continue
        seen_files.add((repo_name, rel))
        repo = repos.get(repo_name)
        if not repo:
            continue
        if not repo.is_git:
            notes.append(f"{repo_name} is not a git clone; no history for owners")
            continue
        for name, email, date in _git_log(repo.path, rel):
            if BOT.search(email) or BOT.search(name):
                continue
            o = owners.setdefault((email or name).lower(), Owner(name=name, email=email))
            try:
                age = (today - dt.date.fromisoformat(date)).days
            except ValueError:
                age = 3650
            o.weight += math.pow(0.5, max(age, 0) / HALF_LIFE_DAYS)
            o.commits += 1
            o.files[f"{repo_name}/{rel}"] = o.files.get(f"{repo_name}/{rel}", 0) + 1
            o.last = max(o.last, date)
        for pattern, who in reversed(_codeowners(repo.path)):  # last matching rule wins
            if _codeowner_match(pattern, rel):
                for w in who:
                    o = owners.setdefault(w.lower(), Owner(name=w, email=w if "@" in w and not w.startswith("@") else ""))
                    o.codeowner_for.append(f"{repo_name}/{rel}")
                    o.weight += 1.5
                break
    return owners, sorted(set(notes))


def add_pr_people(owners: dict[str, Owner], matches) -> None:
    """Credit PR authors and the reviewers who explained a rejection."""
    for m in matches:
        pr = m.pr
        if m.reason_by and not BOT.search(m.reason_by):
            o = _lookup(owners, m.reason_by)
            o.pr_roles.append(f"{'rejected' if pr.state == 'rejected' else 'pushed back on'} #{pr.number}")
            o.weight += 1.2
        if pr.state == "merged" and pr.author and not BOT.search(pr.author):
            o = _lookup(owners, pr.author)
            o.pr_roles.append(f"wrote #{pr.number}")
            o.weight += 0.8


def _lookup(owners: dict[str, Owner], handle: str) -> Owner:
    h = handle.lower().lstrip("@")
    for o in owners.values():
        local = o.email.split("@")[0].lower() if o.email else ""
        if h in {o.name.lower(), o.email.lower(), local} or o.name.lower().replace(" ", "") == h:
            return o
    return owners.setdefault(h, Owner(name=handle, email=""))


def rank(owners: dict[str, Owner], limit: int = 4) -> list[Owner]:
    return sorted(owners.values(), key=lambda o: (-o.weight, o.name.lower()))[:limit]
