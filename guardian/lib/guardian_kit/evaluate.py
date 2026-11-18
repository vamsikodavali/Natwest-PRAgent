"""Measure retrieval quality against a labelled set of tickets.

"Evidence or silence" applies to the tool itself: this module puts a number on
how often the engine puts the right helper in front of Claude, and how often it
correctly stays silent on tickets nothing in context/ covers.

Case file: a JSON list (or ``{"cases": [...]}``)::

    {
      "id": "mask-oov",
      "ticket": "Make account numbers unreadable in log lines",
      "expect": ["mask_account_number"],          # any of these counts as a hit
      "expect_prs": ["142"],                      # optional
      "expand": "unreadable=mask,redact",         # optional: what the skill's model step would add
      "negative": false                           # true = nothing should be found
    }

An ``expect`` entry may be a symbol name (``mask_account_number``), a path suffix
(``utils/masking.py``) or both (``utils/masking.py:mask_account_number``). A
class name matches its methods.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import history, reuse
from .context import list_repos
from .text import build_query, expand_query

MODES = ("baseline", "expanded")


@dataclass
class CaseResult:
    id: str
    negative: bool
    rank: dict[str, int | None] = field(default_factory=dict)  # mode -> 1-based rank of first hit
    returned: dict[str, int] = field(default_factory=dict)  # mode -> number of candidates
    top: dict[str, str] = field(default_factory=dict)  # mode -> top candidate label
    pr_found: dict[str, bool | None] = field(default_factory=dict)
    concepts: list[str] = field(default_factory=list)


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases", []) if isinstance(data, dict) else data
    out = []
    for i, c in enumerate(cases):
        if not isinstance(c, dict) or not (c.get("ticket") or c.get("ticket_file")):
            raise ValueError(f"case #{i + 1} in {path.name} needs a 'ticket'")
        if c.get("ticket_file"):
            c = {**c, "ticket": (path.parent / c["ticket_file"]).read_text(encoding="utf-8")}
        if not c.get("negative") and not c.get("expect"):
            raise ValueError(f"case '{c.get('id', i + 1)}' needs 'expect' or 'negative': true")
        out.append({"id": str(c.get("id", i + 1)), **c})
    return out


def _matches(target: str, cand: reuse.Candidate) -> bool:
    sym = cand.symbol
    path_part, _, name_part = target.rpartition(":") if ":" in target else ("", "", target)
    if not path_part and ("/" in name_part or "." in name_part):
        path_part, name_part = name_part, ""
    if name_part and name_part not in {sym.name, sym.parent} and name_part not in cand.siblings:
        return False
    if path_part:
        full = f"{sym.repo}/{sym.path}"
        if not (full.endswith(path_part.lstrip("/")) or sym.path.endswith(path_part.lstrip("/"))):
            return False
    return True


def _first_hit(expect: list[str], cands: list[reuse.Candidate]) -> int | None:
    for i, c in enumerate(cands, 1):
        if any(_matches(t, c) for t in expect):
            return i
    return None


def run(context: Path, cases: list[dict], limit: int = 5, modes=MODES) -> tuple[list[CaseResult], dict]:
    t0 = time.perf_counter()
    indexes = [reuse.index_repo(context, r) for r in list_repos(context)]
    prs, _ = history.load_prs(context)
    results: list[CaseResult] = []
    for case in cases:
        res = CaseResult(case["id"], bool(case.get("negative")))
        for mode in modes:
            q = build_query(case["ticket"])
            if mode == "expanded":
                expand_query(q, case.get("expand", ""))
            if mode == "baseline":
                res.concepts = [q.concepts[c] for c in sorted(q.concepts)]
            cands, _ = reuse.search(context, q, limit=limit, indexes=indexes, with_call_sites=False)
            res.returned[mode] = len(cands)
            res.top[mode] = (f"{cands[0].symbol.parent + '.' if cands[0].symbol.kind == 'method' and cands[0].symbol.parent else ''}"
                             f"{cands[0].symbol.name}") if cands else "-"
            res.rank[mode] = None if res.negative else _first_hit(case["expect"], cands)
            if case.get("expect_prs"):
                related = [c.symbol.path for c in cands]
                found = {m.pr.number for m in history.search(prs, q, limit=limit, related_files=related)}
                res.pr_found[mode] = all(str(n).lstrip("#") in found for n in case["expect_prs"])
        results.append(res)
    return results, summarize(results, modes, limit, time.perf_counter() - t0)


def summarize(results: list[CaseResult], modes, limit: int, seconds: float) -> dict:
    pos = [r for r in results if not r.negative]
    neg = [r for r in results if r.negative]
    out: dict = {"cases": len(results), "positives": len(pos), "negatives": len(neg),
                 "seconds": round(seconds, 2), "modes": {}}
    for m in modes:
        ranks = [r.rank.get(m) for r in pos]
        prs = [r.pr_found[m] for r in results if m in r.pr_found]

        def at(k, ranks=ranks):
            return sum(1 for x in ranks if x is not None and x <= k) / len(ranks) if ranks else None

        out["modes"][m] = {
            "recall@1": at(1),
            "recall@3": at(3),
            f"recall@{limit}": at(limit),
            "mrr": sum(1 / x for x in ranks if x) / len(ranks) if ranks else None,
            "silent_on_negatives": sum(1 for r in neg if r.returned.get(m, 0) == 0) / len(neg) if neg else None,
            "pr_recall": sum(prs) / len(prs) if prs else None,
            "avg_candidates": sum(r.returned.get(m, 0) for r in results) / len(results) if results else 0,
        }
    return out


def _pct(v) -> str:
    return "n/a" if v is None else f"{v * 100:.0f}%"


def render(results: list[CaseResult], summary: dict, modes, limit: int) -> str:
    lines = [f"## Retrieval eval: {summary['positives']} tickets with a known answer, "
             f"{summary['negatives']} with none ({summary['seconds']}s)", ""]
    head = "| metric | " + " | ".join(modes) + " |"
    lines += [head, "|---" * (len(modes) + 1) + "|"]
    for key, label in (("recall@1", "right helper ranked 1st"), ("recall@3", "right helper in top 3"),
                       (f"recall@{limit}", f"right helper in top {limit}"), ("mrr", "mean reciprocal rank"),
                       ("silent_on_negatives", "silent when nothing exists"),
                       ("pr_recall", "expected PRs surfaced")):
        vals = [summary["modes"][m][key] for m in modes]
        fmt = [f"{v:.2f}" if key == "mrr" and v is not None else _pct(v) for v in vals]
        lines.append(f"| {label} | " + " | ".join(fmt) + " |")
    lines += ["", "| case | " + " | ".join(f"{m} rank" for m in modes) + " | top hit (" + modes[-1] + ") |",
              "|---" * (len(modes) + 2) + "|"]
    for r in results:
        cells = []
        for m in modes:
            if r.negative:
                cells.append("silent ✓" if r.returned.get(m, 0) == 0 else f"✗ {r.returned[m]} returned")
            else:
                cells.append(f"{r.rank[m]}" if r.rank.get(m) else "✗ miss")
        lines.append(f"| {r.id} | " + " | ".join(cells) + f" | {r.top.get(modes[-1], '-')} |")
    misses = [r for r in results if not r.negative and not r.rank.get(modes[-1])]
    if misses:
        lines += ["", "Misses (what the engine heard):"]
        lines += [f"- {r.id}: concepts = {', '.join(r.concepts)}" for r in misses]
    return "\n".join(lines)
