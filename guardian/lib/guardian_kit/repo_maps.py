"""Reading the per-repo file/folder breakdown documents.

Each repository may come with a Markdown breakdown that says what lives where.
Those descriptions are written for humans in plain words, which is exactly the
vocabulary a ticket uses, so a file the breakdown describes as "masks account
numbers for logs" should rank even if the code itself calls it ``obf_acct``.

We look for, in order:

* ``context/repos/<name>.md`` (sibling of the clone)
* ``context/repo-maps/<name>.md`` or ``context/maps/<name>.md``
* inside the clone: any top-level ``*.md`` whose name suggests a breakdown
  (STRUCTURE, BREAKDOWN, REPO_MAP, CODEBASE, ARCHITECTURE, OVERVIEW, LAYOUT, MAP)
* the clone's README as a weak fallback.

Every line that names a path that exists in the repo becomes a description of
that path. A heading that names a path describes everything under it until the
next heading of the same or higher level. Lines that name a symbol in
backticks (``mask_pan()``) describe that symbol.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .context import GUARDIAN_ROOT, Repo

_BREAKDOWN_NAME = re.compile(
    r"(structure|breakdown|repo[-_ ]?map|codebase|architecture|overview|layout|map|files|folders|tree)",
    re.I,
)
_PATHISH = re.compile(r"`([^`\s]+)`|((?:[\w.\-]+/)+[\w.\-]*|[\w\-]+\.[A-Za-z]{1,6}\b)")
_SYMBOLISH = re.compile(r"`([A-Za-z_][\w.]*)\s*(?:\([^`]*\))?`")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_TREE_CHARS = re.compile(r"^[\s│├└─|`+\-\*]+")


@dataclass
class RepoMap:
    sources: list[Path] = field(default_factory=list)
    file_notes: dict[str, list[str]] = field(default_factory=dict)  # relpath -> notes
    dir_notes: dict[str, list[str]] = field(default_factory=dict)  # reldir/ -> notes
    symbol_notes: dict[str, list[str]] = field(default_factory=dict)  # name -> notes
    weak: bool = False  # True when built only from a README

    def notes_for(self, relpath: str) -> tuple[list[str], list[str]]:
        """(notes on the file itself, notes inherited from parent folders)."""
        own = self.file_notes.get(relpath, [])
        inherited: list[str] = []
        parts = relpath.split("/")[:-1]
        for i in range(len(parts), 0, -1):
            inherited.extend(self.dir_notes.get("/".join(parts[:i]) + "/", []))
        return own, inherited


def _data_dirs(context: Path) -> list[Path]:
    """Folders of per-repo documents (policy docs, breakdowns) kept beside the context."""
    out: list[Path] = []
    for d in (context / "data", context.parent / "data", GUARDIAN_ROOT / "data"):
        if d.is_dir() and d.resolve() not in {o.resolve() for o in out}:
            out.append(d)
    return out


def _names_repo(stem: str, repo_name: str) -> bool:
    """`capitalone-locopy_technical_policy` names `locopy`; `capitalone-locopy-v2` does not."""
    return re.search(rf"(^|[-_.]){re.escape(repo_name.lower())}([-_.]|$)", stem.lower()) is not None


def find_map_files(context: Path, repo: Repo) -> tuple[list[Path], bool]:
    found: list[Path] = []
    for cand in (
        context / "repos" / f"{repo.name}.md",
        context / "repo-maps" / f"{repo.name}.md",
        context / "maps" / f"{repo.name}.md",
    ):
        if cand.is_file():
            found.append(cand)
    for d in _data_dirs(context):
        found.extend(sorted(p for p in d.glob("*.md") if _names_repo(p.stem, repo.name)))
    try:
        top_md = sorted(p for p in repo.path.iterdir() if p.is_file() and p.suffix.lower() == ".md")
    except OSError:
        top_md = []
    for p in top_md:
        if _BREAKDOWN_NAME.search(p.stem):
            found.append(p)
    for docs in ("docs", "doc"):
        d = repo.path / docs
        if d.is_dir():
            found.extend(sorted(p for p in d.glob("*.md") if _BREAKDOWN_NAME.search(p.stem)))
    if found:
        return found, False
    readme = next((p for p in top_md if p.stem.lower() == "readme"), None)
    return ([readme], True) if readme else ([], False)


class _PathIndex:
    """Resolve the loose path spellings people write in docs to real repo paths."""

    def __init__(self, relpaths: list[str]):
        self.files = set(relpaths)
        self.dirs: set[str] = set()
        self.by_suffix: dict[str, list[str]] = {}
        for rp in relpaths:
            parts = rp.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]) + "/")
            for i in range(len(parts)):
                self.by_suffix.setdefault("/".join(parts[i:]), []).append(rp)

    def resolve(self, token: str) -> tuple[str | None, bool]:
        """Return (path, is_dir) or (None, False)."""
        t = token.strip().strip("`'\"()[]<>,:;").lstrip("./")
        if not t or len(t) < 3:
            return None, False
        if t.endswith("/"):
            if t in self.dirs:
                return t, True
            hits = [d for d in self.dirs if d.endswith("/" + t)]
            return (hits[0], True) if len(hits) == 1 else (None, False)
        if t in self.files:
            return t, False
        if t + "/" in self.dirs:
            return t + "/", True
        hits = self.by_suffix.get(t, [])
        if len(hits) == 1:
            return hits[0], False
        dir_hits = [d for d in self.dirs if d.endswith("/" + t + "/")]
        if len(dir_hits) == 1:
            return dir_hits[0], True
        return None, False


def _clean(line: str) -> str:
    line = _TREE_CHARS.sub("", line)
    line = line.replace("|", " ").replace("**", "")
    return re.sub(r"\s+", " ", line).strip()


# In long policy / engineering documents only these sections say what code *does*.
# Security, cost, testing or "gaps" sections also name files, but attaching those
# lines to code turns every file into a match for every ticket.
_DESCRIPTIVE_SECTION = re.compile(
    r"architecture|structure|layout|module|component|reus|capabilit|breakdown|overview of (the )?code|"
    r"files?\b|folders?|director|package|entry points?|code ?map|what lives where",
    re.I,
)


def _section_filter(text: str):
    """Return a predicate over top-level (#/##) headings, or None to keep every section."""
    tops = [m.group(2) for m in (_HEADING.match(line) for line in text.splitlines()) if m and len(m.group(1)) <= 2]
    sections = tops[1:] if len(tops) > 1 else tops  # the first heading is usually the title
    descriptive = [t for t in sections if _DESCRIPTIVE_SECTION.search(t)]
    if len(sections) < 6 or not descriptive:
        return None  # a short breakdown file, or nothing to choose: use it all
    return lambda heading: bool(_DESCRIPTIVE_SECTION.search(heading))


def parse_map(text: str, index: _PathIndex, rmap: RepoMap) -> None:
    heading_stack: list[tuple[int, list[tuple[str, bool]]]] = []
    in_fence = False
    keep_section = _section_filter(text)
    in_kept = keep_section is None
    for raw in text.splitlines():
        if raw.strip().startswith("```"):
            in_fence = not in_fence
            continue
        h = _HEADING.match(raw) if not in_fence else None
        if keep_section is not None and h and len(h.group(1)) <= 2:
            in_kept = keep_section(h.group(2))
        if not in_kept:
            continue
        targets: list[tuple[str, bool]] = []
        stripped = raw
        for m in _PATHISH.finditer(raw):
            tok = m.group(1) or m.group(2)
            path, is_dir = index.resolve(tok)
            if path:
                targets.append((path, is_dir))
                stripped = stripped.replace(m.group(0), " ", 1)
        if h:
            level = len(h.group(1))
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, targets))
            note = _clean(_HEADING.match(stripped).group(2) if _HEADING.match(stripped) else stripped)
        else:
            note = _clean(stripped)
        note = note.strip(" -:–—")
        if not note:
            continue
        inherited = [t for _, ts in heading_stack for t in ts] if not h else []
        for path, is_dir in targets or inherited:
            bucket = rmap.dir_notes if is_dir else rmap.file_notes
            bucket.setdefault(path, []).append(note)
        for m in _SYMBOLISH.finditer(raw):
            name = m.group(1).split(".")[-1]
            if "/" not in m.group(1) and not re.search(r"\.[A-Za-z]{1,6}$", m.group(1)):
                rmap.symbol_notes.setdefault(name, []).append(note)


def load_repo_map(context: Path, repo: Repo, relpaths: list[str]) -> RepoMap:
    files, weak = find_map_files(context, repo)
    rmap = RepoMap(sources=files, weak=weak)
    if not files:
        return rmap
    index = _PathIndex(relpaths)
    for f in files:
        try:
            parse_map(f.read_text(encoding="utf-8", errors="replace"), index, rmap)
        except OSError:
            continue
    return rmap
