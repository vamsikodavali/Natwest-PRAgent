"""Reuse search: "did we already build this?"

Ranking, per symbol::

    score = sum over matched query concepts of
              concept weight * idf * best field weight
                (name 3.0, breakdown-doc note 2.2, doc comment 1.4, path 0.9)
            * coverage factor   (share of the ticket's concepts it touches)
            * penalties         (test code, private helpers, files the diff itself touches)

A concept counts once, through its strongest field, so a helper named
``mask_account_number`` beats a file that says "account" fifty times.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .code_index import (
    SourceFile,
    Symbol,
    all_relpaths,
    extract_symbols,
    find_call_sites,
    import_hint,
    iter_source_files,
)
from .context import Repo, list_repos
from .repo_maps import RepoMap, load_repo_map
from .text import Query, stem_set

FIELD_WEIGHTS = {"name": 3.0, "map": 2.2, "doc": 1.4, "path": 0.9}
TEST_PENALTY = 0.3
PRIVATE_PENALTY = 0.8
DIFF_FILE_PENALTY = 0.5
NONPROD_PENALTY = 0.5
NONPROD_PATH = re.compile(r"(^|/)(docs?|scripts?|examples?|samples?|benchmarks?|bench|sandbox|demos?|playground)(/|$)", re.I)
RELATIVE_CUTOFF = 0.4  # drop candidates scoring under 40% of the best one
MIN_CONFIDENCE = 0.08  # floor on score / best possible score (every concept in the name)
NAME_PRECISION_BASE, NAME_PRECISION_GAIN = 0.9, 0.3  # x0.9 (name unexplained) .. x1.2 (fully explained); tuned with `guardian eval`
DOC_LENGTH_B = 0.5  # 0 = no length normalisation, 1 = full (BM25 b)
SIBLING_RATIO = 0.75  # a same-file hit this close to the best one gets its own entry (grab-bag utils files)
MIN_CONCEPTS = 2  # a single shared word is not evidence of reuse


@dataclass
class Candidate:
    symbol: Symbol
    score: float
    matched: list[str]
    coverage: float
    confidence: float = 0.0
    call_sites: list[str] = field(default_factory=list)
    import_hint: str = ""
    siblings: list[str] = field(default_factory=list)
    abs_path: str = ""

    def to_dict(self) -> dict:
        s = self.symbol
        return {
            "repo": s.repo,
            "path": s.path,
            "abs_path": self.abs_path,
            "line": s.line,
            "end_line": s.end_line,
            "location": s.location,
            "name": s.name,
            "kind": s.kind,
            "parent": s.parent,
            "signature": s.signature,
            "doc": s.doc,
            "map_note": s.map_note,
            "is_test": s.is_test,
            "score": round(self.score, 2),
            "coverage": round(self.coverage, 2),
            "confidence": round(self.confidence, 2),
            "matched": self.matched,
            "call_sites": self.call_sites,
            "import_hint": self.import_hint,
            "also_in_file": self.siblings,
        }


@dataclass
class RepoIndex:
    repo: Repo
    files: list[SourceFile]
    symbols: list[Symbol]
    repo_map: RepoMap


def index_repo(context: Path, repo: Repo) -> RepoIndex:
    files = list(iter_source_files(repo))
    rmap = load_repo_map(context, repo, all_relpaths(repo))
    symbols: list[Symbol] = []
    for f in files:
        file_symbols = extract_symbols(f)
        own, inherited = rmap.notes_for(f.relpath)
        path_stems = stem_set(f.relpath.rsplit(".", 1)[0])
        for sym in file_symbols:
            sym.name_stems = stem_set(sym.name)
            sym.doc_stems = stem_set(sym.doc + " " + sym.signature) - sym.name_stems
            sym.path_stems = path_stems | (stem_set(sym.parent) if sym.parent else set())
            # A README-only map is prose about the project, not a breakdown: only trust
            # lines that name this exact file or symbol, and never show them as a summary.
            notes = rmap.symbol_notes.get(sym.name, []) + own + ([] if rmap.weak else inherited[:2])
            if notes:
                sym.map_stems = stem_set(" ".join(notes))
                if not rmap.weak:
                    sym.map_note = notes[0][:200]
        symbols.extend(file_symbols)
    return RepoIndex(repo, files, symbols, rmap)


def _idf(symbols: list[Symbol], query: Query) -> tuple[dict[str, float], set[str]]:
    """(BM25-style idf per query term, terms that occur anywhere in the corpus)."""
    df: Counter[str] = Counter()
    for s in symbols:
        bag = s.name_stems | s.doc_stems | s.path_stems | s.map_stems
        for t in query.terms:
            if t in bag:
                df[t] += 1
    n = max(len(symbols), 1)
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in query.terms}
    return idf, {t for t in query.terms if df[t]}


def _ideal_score(query: Query, idf: dict[str, float], present: set[str]) -> float:
    """Score of an imaginary symbol whose name holds every *matchable* ticket concept.

    Concepts no symbol in any repo mentions ("hiccup", "Christmas") can't be matched
    by anything, so they must not drag every candidate under the noise floor.
    """
    best: dict[int, float] = {}
    for term, (concept, weight) in query.terms.items():
        if concept in query.hints or term not in present:
            continue
        best[concept] = max(best.get(concept, 0.0), weight * idf.get(term, 1.0) * FIELD_WEIGHTS["name"])
    return sum(best.values()) * 1.4


def score_symbol(sym: Symbol, query: Query, idf: dict[str, float], avg_doc: float = 0.0) -> tuple[float, list[str], float]:
    # BM25-style length normalisation: a word in a 4-line docstring says more than
    # the same word somewhere in a 60-line one.
    doc_norm = 1.0
    if avg_doc and sym.doc_stems:
        doc_norm = 1.0 / (1 - DOC_LENGTH_B + DOC_LENGTH_B * len(sym.doc_stems) / avg_doc)
    best: dict[int, tuple[float, str]] = {}
    for term, (concept, weight) in query.terms.items():
        fw = 0.0
        if term in sym.name_stems:
            fw = FIELD_WEIGHTS["name"]
        elif term in sym.map_stems:
            fw = FIELD_WEIGHTS["map"]
        elif term in sym.doc_stems:
            fw = FIELD_WEIGHTS["doc"] * min(doc_norm, 1.5)
        elif term in sym.path_stems:
            fw = FIELD_WEIGHTS["path"]
        if not fw:
            continue
        val = weight * idf.get(term, 1.0) * fw
        if concept not in best or val > best[concept][0]:
            best[concept] = (val, term)
    if not best:
        return 0.0, [], 0.0
    raw = sum(v for v, _ in best.values())
    coverage = query.primary_hits(best) / max(query.concept_count, 1)
    score = raw * (0.4 + coverage)
    # How much of the *name* the ticket explains: `PetValidator` for "validate a pet"
    # is 2/2; `AxiosError`, which only matches through a long docstring, is 0/2.
    if sym.name_stems:
        name_precision = len(sym.name_stems & query.terms.keys()) / len(sym.name_stems)
        score *= NAME_PRECISION_BASE + NAME_PRECISION_GAIN * name_precision
    if query.identifiers and sym.name in query.identifiers:
        score += 6.0
    if sym.is_test:
        score *= TEST_PENALTY
    if NONPROD_PATH.search(sym.path):
        score *= NONPROD_PENALTY
    if sym.name.startswith("_") and not sym.name.startswith("__"):
        score *= PRIVATE_PENALTY
    if any(sym.path == f or f.endswith("/" + sym.path) or sym.path.endswith("/" + f) for f in query.diff_files):
        score *= DIFF_FILE_PENALTY
    matched = [query.concepts[c] if query.concepts[c] == t else f"{query.concepts[c]}~{t}" for c, (_, t) in sorted(best.items())]
    return score, matched, coverage


def search(
    context: Path,
    query: Query,
    limit: int = 6,
    repos: list[str] | None = None,
    include_tests: bool = False,
    with_call_sites: bool = True,
    indexes: list[RepoIndex] | None = None,
) -> tuple[list[Candidate], dict]:
    """Rank symbols across all repos. Returns (candidates, stats)."""
    if indexes is None:
        indexes = [index_repo(context, r) for r in list_repos(context, repos)]
    symbols = [s for ix in indexes for s in ix.symbols]
    idf, present = _idf(symbols, query)
    documented = [len(s.doc_stems) for s in symbols if s.doc_stems]
    avg_doc = sum(documented) / len(documented) if documented else 0.0
    ideal = _ideal_score(query, idf, present)

    scored: list[Candidate] = []
    for s in symbols:
        if s.is_test and not include_tests:
            continue
        score, matched, coverage = score_symbol(s, query, idf, avg_doc)
        min_concepts = min(MIN_CONCEPTS, query.concept_count)
        exact = bool(query.identifiers) and s.name in query.identifiers
        # `throttle()`, `speedometer()`: one concept, but it *is* the whole name
        # and lives in a module named after it (helpers/throttle.js), not a generic method
        whole_name = (bool(s.name_stems) and s.name_stems <= set(query.terms) and s.kind != "method"
                      and Path(s.path).stem.lower().replace("_", "") == s.name.lower().replace("_", ""))
        if score <= 0 or (len(matched) < min_concepts and not (exact or whole_name)):
            continue
        confidence = min(score / ideal, 1.0) if ideal else 0.0
        if confidence < MIN_CONFIDENCE:
            continue
        scored.append(Candidate(s, score, matched, coverage, confidence))
    scored.sort(key=lambda c: (-c.score, c.symbol.repo, c.symbol.path, c.symbol.line))

    # one entry per file: weaker hits in the same file become "also here" siblings
    out: list[Candidate] = []
    by_file: dict[tuple[str, str], Candidate] = {}
    top = scored[0].score if scored else 0.0
    for c in scored:
        if c.score < top * RELATIVE_CUTOFF:
            break
        key = (c.symbol.repo, c.symbol.path)
        if key in by_file and c.score < by_file[key].score * SIBLING_RATIO:
            lead = by_file[key]
            label = c.symbol.parent if c.symbol.kind == "method" and c.symbol.parent else c.symbol.name
            lead_label = lead.symbol.parent if lead.symbol.kind == "method" else lead.symbol.name
            if label not in lead.siblings and label != lead_label and len(lead.siblings) < 3:
                lead.siblings.append(label)
            continue
        if len(out) >= limit:
            continue
        by_file.setdefault(key, c)
        out.append(c)

    if with_call_sites:
        by_repo = {ix.repo.name: ix.files for ix in indexes}
        for c in out:
            c.call_sites = find_call_sites(by_repo.get(c.symbol.repo, []), c.symbol)
            c.import_hint = import_hint(c.symbol)

    roots = {ix.repo.name: ix.repo.path for ix in indexes}
    for c in out:
        c.abs_path = str(roots[c.symbol.repo] / c.symbol.path)

    stats = {
        "repos": [ix.repo.name for ix in indexes],
        "files_indexed": sum(len(ix.files) for ix in indexes),
        "symbols_indexed": len(symbols),
        "repo_maps": {ix.repo.name: [str(p) for p in ix.repo_map.sources] for ix in indexes},
        "query_concepts": [query.concepts[c] for c in sorted(query.concepts)],
    }
    return out, stats
