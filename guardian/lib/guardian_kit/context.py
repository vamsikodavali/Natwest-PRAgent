"""Locating the engineering-memory folder and the repositories inside it.

Layout (see the project README)::

    context/
      repos/<name>/          cloned repositories
      repos/<name>.md        optional file/folder breakdown for <name>
      prs/**/*.json          exported pull requests
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GUARDIAN_ROOT = Path(__file__).resolve().parents[2]


class ContextError(RuntimeError):
    """The context folder is missing or unusable. Message is user-facing."""


@dataclass(frozen=True)
class Repo:
    name: str
    path: Path

    @property
    def is_git(self) -> bool:
        return (self.path / ".git").exists()


def resolve_context(explicit: str | None = None) -> Path:
    """``--context`` flag, then ``$GUARDIAN_CONTEXT``, then ``<guardian>/context``."""
    raw = explicit or os.environ.get("GUARDIAN_CONTEXT") or str(GUARDIAN_ROOT / "context")
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise ContextError(
            f"context folder not found: {path}\n"
            "Clone repositories into context/repos/ and export PRs into context/prs/, "
            "or point GUARDIAN_CONTEXT at another folder."
        )
    return path


def list_repos(context: Path, only: list[str] | None = None) -> list[Repo]:
    repos_dir = context / "repos"
    if not repos_dir.is_dir():
        return []
    wanted = {o.lower() for o in only} if only else None
    out = []
    for child in sorted(repos_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if wanted and child.name.lower() not in wanted:
            continue
        out.append(Repo(child.name, child))
    return out
