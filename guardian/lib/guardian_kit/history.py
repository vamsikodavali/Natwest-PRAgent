"""PR history search: "was this tried or rejected before?"

Exports differ (``gh pr view --json``, the GitHub REST API, GitLab, Bitbucket,
hand-written fixtures), so loading is deliberately forgiving: each JSON file
may hold one PR, a list, or a wrapper object, and field names are mapped
through a list of known aliases. Anything unparsable becomes a warning, never
a crash.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .text import Query, stem_set

FIELD_WEIGHTS = {"title": 3.0, "labels": 2.0, "files": 1.6, "body": 1.0, "discussion": 0.6}
FILE_OVERLAP_BONUS = 4.0
DIR_OVERLAP_BONUS = 1.0
RELATIVE_CUTOFF = 0.3
MIN_CONCEPTS = 2

REJECT_STATES = {"closed", "declined", "rejected", "abandoned", "superseded"}
CHANGE_REQUEST_STATES = {"changes_requested", "request_changes", "rejected", "needs_work", "declined"}
REASON_CUES = re.compile(
    r"\b(reject\w*|closing|close this|duplicate\w*|already (?:exists?|have|has)|instead|"
    r"please (?:use|reuse)|reuse|don't|do not|must not|never|not needed|won'?t|wontfix|superseded|"
    r"violat\w*|policy|polic\w+|security|complian\w*|pii|cost\w*|expensive|blocked|not approved|"
    r"we already|existing)\b",
    re.I,
)
BOT = re.compile(r"(\[bot\]|-bot\b|\bbot$|dependabot|renovate|github-actions|codecov|sonar)", re.I)


@dataclass
class Remark:
    author: str
    body: str
    state: str = ""
    date: str = ""


@dataclass
class PullRequest:
    number: str
    title: str
    body: str
    state: str  # merged | rejected | open
    raw_state: str
    files: list[str]
    remarks: list[Remark]
    author: str = ""
    url: str = ""
    repo: str = ""
    labels: list[str] = field(default_factory=list)
    date: str = ""
    explicit_reason: str = ""
    source: str = ""

    def reviewers(self) -> list[str]:
        seen: list[str] = []
        for r in self.remarks:
            if r.author and r.author != self.author and r.author not in seen and not BOT.search(r.author):
                seen.append(r.author)
        return seen


# ---------------------------------------------------------------- loading

def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return default


def _person(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(_first(v, "login", "username", "name", "display_name", "displayName", "email", default=""))
    return ""


def _text(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(_first(v, "raw", "body", "text", "content", "markdown", default=""))
    return ""


def _files(v) -> list[str]:
    out: list[str] = []
    if isinstance(v, dict):
        v = _first(v, "nodes", "items", "values", default=list(v.keys()))
    for f in v or []:
        if isinstance(f, str):
            out.append(f)
        elif isinstance(f, dict):
            p = _first(f, "path", "filename", "file", "new_path", "newPath", "name")
            if isinstance(p, dict):
                p = _first(p, "toString", "path", "name")
            if p:
                out.append(str(p))
    return out


def _remarks(d: dict) -> list[Remark]:
    out: list[Remark] = []
    for key in ("reviews", "comments", "review_comments", "reviewComments", "discussion", "notes",
                "activities", "timeline", "conversation", "feedback"):
        items = d.get(key)
        if isinstance(items, dict):
            items = _first(items, "nodes", "items", "values", default=[])
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, str):
                out.append(Remark("", it))
                continue
            if not isinstance(it, dict):
                continue
            inner = it.get("comment") if isinstance(it.get("comment"), dict) else it
            body = _text(_first(inner, "body", "text", "content", "comment", "note", "message", default=""))
            state = str(_first(it, "state", "status", "action", "decision", default="")).lower()
            if not body and not state:
                continue
            out.append(
                Remark(
                    author=_person(_first(inner, "author", "user", "reviewer", "by", default="")),
                    body=body.strip(),
                    state=state,
                    date=str(_first(inner, "submittedAt", "submitted_at", "createdAt", "created_at", "created_on", "date", default="")),
                )
            )
    return out


def _state(d: dict) -> tuple[str, str]:
    raw = str(_first(d, "state", "status", default="")).lower()
    merged = d.get("merged") is True or (bool(_first(d, "mergedAt", "merged_at", "mergedBy", default=None)) and raw != "open")
    if raw in {"merged"} or merged:
        return "merged", raw or "merged"
    if raw in REJECT_STATES or d.get("rejected") is True:
        return "rejected", raw
    if str(_first(d, "outcome", "decision", default="")).lower() in {"rejected", "declined", "closed"}:
        return "rejected", raw or "rejected"
    return "open", raw or "open"


def normalize(d: dict, source: str = "") -> PullRequest | None:
    number = _first(d, "number", "iid", "pr_number", "prNumber", "pr", "id")
    title = _first(d, "title", "name", "summary")
    if number is None or not title:
        return None
    state, raw = _state(d)
    repo = _first(d, "repo", "repository", "project", "base_repo", default="")
    if isinstance(repo, dict):
        repo = _first(repo, "nameWithOwner", "full_name", "name", "slug", default="")
    labels_raw = _first(d, "labels", "tags", default=[]) or []
    labels = [(_person(lb) if isinstance(lb, dict) else str(lb)) for lb in labels_raw] if isinstance(labels_raw, list) else []
    reason = _first(d, "rejection_reason", "rejectionReason", "reject_reason", "close_reason", "closeReason",
                    "reason", "decision_reason", "outcome_reason", default="")
    return PullRequest(
        number=str(number).lstrip("#"),
        title=str(title).strip(),
        body=_text(_first(d, "body", "description", "summary_text", default="")),
        state=state,
        raw_state=raw,
        files=_files(_first(d, "files", "changed_files_list", "changedFiles", "files_changed", "filesChanged",
                            "paths", "diffstat", default=[])),
        remarks=_remarks(d),
        author=_person(_first(d, "author", "user", "creator", "opened_by", default="")),
        url=str(_first(d, "url", "html_url", "web_url", "permalink", "link", default="")),
        repo=str(repo),
        labels=labels,
        date=str(_first(d, "mergedAt", "merged_at", "closedAt", "closed_at", "updatedAt", "createdAt", "created_at", default="")),
        explicit_reason=_text(reason) if not isinstance(reason, (int, float)) else "",
        source=source,
    )


def _unwrap(data) -> list[dict]:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        for k in ("pullRequests", "pull_requests", "prs", "items", "values", "data", "nodes", "results"):
            inner = data.get(k)
            if isinstance(inner, list):
                return [d for d in inner if isinstance(d, dict)]
            if isinstance(inner, dict) and k == "data":
                return _unwrap(inner)
        return [data]
    return []


def load_prs(context: Path) -> tuple[list[PullRequest], list[str]]:
    prs_dir = context / "prs"
    prs: list[PullRequest] = []
    warnings: list[str] = []
    if not prs_dir.is_dir():
        return prs, [f"no PR folder at {prs_dir}"]
    seen: set[tuple[str, str]] = set()
    for f in sorted(prs_dir.rglob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as e:
            warnings.append(f"skipped {f.name}: {e.__class__.__name__}: {e}")
            continue
        repo_hint = f.parent.name if f.parent != prs_dir else ""
        for d in _unwrap(data):
            pr = normalize(d, source=str(f))
            if not pr:
                warnings.append(f"skipped an entry in {f.name}: no number or title")
                continue
            pr.repo = pr.repo or repo_hint
            key = (pr.repo, pr.number)
            if key in seen:
                continue
            seen.add(key)
            prs.append(pr)
    return prs, warnings


# ---------------------------------------------------------------- reasons

def _sentences(text: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`\"'(])", text) if s.strip()]


def _trim(text: str, limit: int = 220) -> str:
    sents = _sentences(text)
    out = ""
    for s in sents:
        if len(out) + len(s) + 1 > limit and out:
            break
        out = (out + " " + s).strip()
    if len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


def rejection_reason(pr: PullRequest) -> tuple[str, str]:
    """(reason, who said it). Empty strings if nothing credible was found."""
    if pr.explicit_reason:
        return _trim(pr.explicit_reason), next(iter(pr.reviewers()), "")
    best: tuple[float, int, Remark] | None = None
    for i, r in enumerate(pr.remarks):
        if not r.body or BOT.search(r.author or ""):
            continue
        score = 0.0
        if r.state in CHANGE_REQUEST_STATES:
            score += 3.0
        cues = len(REASON_CUES.findall(r.body))
        score += min(cues, 4) * 1.0
        if r.author and r.author != pr.author:
            score += 1.0
        elif r.author and r.author == pr.author:
            score -= 1.5  # the author's own reply rarely states the decision
        if score <= 0.5:
            continue
        cand = (score, i, r)  # later remark wins ties: closer to the decision
        if best is None or (score, i) > (best[0], best[1]):
            best = cand
    if not best:
        return "", ""
    r = best[2]
    body = " ".join(_sentences(r.body))
    if len(body) <= 220:
        return body, r.author
    cue_sents = [s for s in _sentences(r.body) if REASON_CUES.search(s)]
    return _trim(" ".join(cue_sents) or r.body), r.author


# ---------------------------------------------------------------- search

@dataclass
class Match:
    pr: PullRequest
    score: float
    matched: list[str]
    shared_files: list[str]
    reason: str = ""
    reason_by: str = ""

    def to_dict(self) -> dict:
        p = self.pr
        return {
            "number": p.number,
            "title": p.title,
            "state": p.state,
            "raw_state": p.raw_state,
            "repo": p.repo,
            "url": p.url,
            "author": p.author,
            "reviewers": p.reviewers()[:4],
            "date": p.date,
            "files": p.files[:8],
            "shared_files": self.shared_files,
            "reason": self.reason,
            "reason_by": self.reason_by,
            "score": round(self.score, 2),
            "matched": self.matched,
            "source": p.source,
        }


def _fields(pr: PullRequest) -> dict[str, set[str]]:
    return {
        "title": stem_set(pr.title),
        "labels": stem_set(" ".join(pr.labels)),
        "files": stem_set(" ".join(f.rsplit(".", 1)[0] for f in pr.files)),
        "body": stem_set(pr.body[:6000]),
        "discussion": stem_set(" ".join(r.body for r in pr.remarks)[:8000]),
    }


def _path_match(a: str, b: str) -> bool:
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def search(
    prs: list[PullRequest],
    query: Query,
    limit: int = 5,
    related_files: list[str] | None = None,
    state: str | None = None,
) -> list[Match]:
    related_files = related_files or []
    fields = [_fields(p) for p in prs]
    n = max(len(prs), 1)
    df: Counter[str] = Counter()
    for fs in fields:
        bag = set().union(*fs.values())
        for t in query.terms:
            if t in bag:
                df[t] += 1
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in query.terms}

    out: list[Match] = []
    for pr, fs in zip(prs, fields):
        if state and pr.state != state:
            continue
        if pr.author and BOT.search(pr.author):
            continue  # dependency bumps and bot PRs are never design precedent
        best: dict[int, tuple[float, str]] = {}
        for term, (concept, weight) in query.terms.items():
            fw = max((FIELD_WEIGHTS[name] for name, bag in fs.items() if term in bag), default=0.0)
            if fw:
                v = weight * idf[term] * fw
                if concept not in best or v > best[concept][0]:
                    best[concept] = (v, term)
        shared = sorted({f for f in pr.files for r in related_files if _path_match(f, r)})
        shared_dirs = {
            f for f in pr.files for r in related_files
            if "/" in r and "/" in f and f.rsplit("/", 1)[0].endswith(r.rsplit("/", 1)[0].split("/")[-1])
        }
        if not best and not shared:
            continue
        if len(best) < min(MIN_CONCEPTS, query.concept_count) and not shared:
            continue
        coverage = query.primary_hits(best) / max(query.concept_count, 1)
        score = sum(v for v, _ in best.values()) * (0.4 + coverage)
        score += FILE_OVERLAP_BONUS * min(len(shared), 2) + (DIR_OVERLAP_BONUS if shared_dirs and not shared else 0)
        matched = [query.concepts[c] for c in sorted(best)]
        out.append(Match(pr, score, matched, shared[:3]))

    out.sort(key=lambda m: (-m.score, m.pr.repo, m.pr.number))
    if out:
        top = out[0].score
        out = [m for m in out if m.score >= top * RELATIVE_CUTOFF][:limit]
    for m in out:
        if m.pr.state == "rejected" or any(r.state in CHANGE_REQUEST_STATES for r in m.pr.remarks):
            m.reason, m.reason_by = rejection_reason(m.pr)
    return out
