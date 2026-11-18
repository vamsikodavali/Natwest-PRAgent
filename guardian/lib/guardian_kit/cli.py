"""``guardian`` command line. Every subcommand prints Markdown (default) or JSON.

Exit codes: 0 ok (including "no matches"), 2 bad input or missing context.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, history, owners, reuse
from .blueprint import (
    render_blueprint,
    render_owners,
    render_prs,
    render_reuse,
    run_blueprint,
    run_history,
    run_reuse,
    ticket_title,
)
from .context import ContextError, list_repos, resolve_context
from .repo_maps import find_map_files
from .text import build_query


def _read_input(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    text = " ".join(args.text or [])
    if (not args.text or args.text == ["-"]) and not sys.stdin.isatty():
        text = sys.stdin.read()
    return text


def _emit(args, payload: dict, markdown: str) -> None:
    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(markdown.rstrip() + "\n")


def _add_common(p: argparse.ArgumentParser, with_input: bool = True) -> None:
    p.add_argument("--context", help="context folder (default: $GUARDIAN_CONTEXT or <guardian>/context)")
    p.add_argument("--format", choices=("md", "json"), default="md")
    if with_input:
        p.add_argument("--file", help="read the ticket, description or diff from this file")
        p.add_argument("text", nargs="*", help="ticket text, feature description or unified diff ('-' = stdin)")


def cmd_reuse(args, ctx: Path, text: str) -> int:
    q = build_query(text)
    cands, stats = run_reuse(ctx, q, args.limit, repos=args.repo, include_tests=args.include_tests)
    payload = {"query": stats["query_concepts"], "candidates": [c.to_dict() for c in cands], "stats": stats}
    _emit(args, payload, "### Reuse candidates\n" + "\n".join(render_reuse(payload["candidates"])))
    return 0


def cmd_history(args, ctx: Path, text: str) -> int:
    q = build_query(text)
    matches, warnings, n = run_history(ctx, q, args.limit, related_files=args.related_file, state=args.state)
    payload = {"query": [q.concepts[c] for c in sorted(q.concepts)], "prs": [m.to_dict() for m in matches],
               "prs_loaded": n, "warnings": warnings}
    _emit(args, payload, "### Reference PRs\n" + "\n".join(render_prs(payload["prs"])))
    return 0


def cmd_owners(args, ctx: Path) -> int:
    repos = {r.name: r for r in list_repos(ctx)}
    files = []
    for spec in args.paths:
        repo, _, rel = spec.partition("/")
        if repo not in repos or not rel:
            print(f"guardian: '{spec}' must be <repo>/<path> with <repo> in {ctx / 'repos'}", file=sys.stderr)
            return 2
        files.append((repo, rel))
    found, notes = owners.find_owners(repos, files)
    ranked = owners.rank(found, args.limit)
    payload = {"owners": [o.to_dict() for o in ranked], "notes": notes}
    _emit(args, payload, "### Who to ask\n" + "\n".join(render_owners(payload["owners"])))
    return 0


def cmd_blueprint(args, ctx: Path, text: str) -> int:
    q = build_query(text)
    bp = run_blueprint(ctx, q, reuse_limit=args.limit, pr_limit=args.pr_limit, owner_limit=args.owner_limit,
                       repos=args.repo)
    _emit(args, bp, render_blueprint(bp, ticket_title(text)))
    return 0


def cmd_doctor(args, ctx: Path) -> int:
    """Check the context is usable before a demo."""
    repos = list_repos(ctx)
    prs, warnings = history.load_prs(ctx)
    report = {"context": str(ctx), "repos": [], "prs_loaded": len(prs), "pr_states": {}, "warnings": warnings}
    for p in prs:
        report["pr_states"][p.state] = report["pr_states"].get(p.state, 0) + 1
    with_reason = sum(1 for p in prs if p.state == "rejected" and history.rejection_reason(p)[0])
    report["rejected_with_reason"] = with_reason
    for r in repos:
        ix = reuse.index_repo(ctx, r)
        maps, weak = find_map_files(ctx, r)
        report["repos"].append({
            "name": r.name, "git": r.is_git, "files": len(ix.files), "symbols": len(ix.symbols),
            "breakdown_docs": [str(m.relative_to(ctx)) if m.is_relative_to(ctx) else str(m) for m in maps],
            "breakdown_is_readme_only": weak,
            "described_paths": len(ix.repo_map.file_notes) + len(ix.repo_map.dir_notes),
        })
    lines = [f"context: {ctx}", f"repos: {len(repos)}"]
    for r in report["repos"]:
        flag = "" if r["git"] else "  (not a git clone: no owners)"
        doc = ", ".join(r["breakdown_docs"]) or "none"
        lines.append(f"  - {r['name']}: {r['files']} files, {r['symbols']} symbols, breakdown: {doc}"
                     f" ({r['described_paths']} paths described){flag}")
    lines.append(f"prs: {len(prs)} {report['pr_states']}, rejected with a findable reason: {with_reason}")
    lines.extend(f"warning: {w}" for w in warnings)
    if not repos:
        lines.append("problem: no repositories under context/repos/")
    if not prs:
        lines.append("problem: no pull requests under context/prs/")
    _emit(args, report, "\n".join(lines))
    return 0 if repos else 2


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="guardian", description="Reuse, PR history and ownership search over context/.")
    ap.add_argument("--version", action="version", version=f"guardian {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("reuse", help="find existing code that already does this")
    _add_common(p)
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--repo", action="append", help="limit to this repo (repeatable)")
    p.add_argument("--include-tests", action="store_true")

    p = sub.add_parser("history", help="find similar past pull requests")
    _add_common(p)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--state", choices=("merged", "rejected", "open"))
    p.add_argument("--related-file", action="append", help="boost PRs that touched this path (repeatable)")

    p = sub.add_parser("owners", help="who knows these files")
    _add_common(p, with_input=False)
    p.add_argument("paths", nargs="+", help="<repo>/<path> as printed by `reuse`")
    p.add_argument("--limit", type=int, default=4)

    p = sub.add_parser("blueprint", help="reuse + history + owners for a ticket")
    _add_common(p)
    p.add_argument("--limit", type=int, default=4, help="reuse candidates")
    p.add_argument("--pr-limit", type=int, default=4)
    p.add_argument("--owner-limit", type=int, default=3)
    p.add_argument("--repo", action="append")

    p = sub.add_parser("doctor", help="check that context/ is ready")
    _add_common(p, with_input=False)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = resolve_context(args.context)
    except ContextError as e:
        print(f"guardian: {e}", file=sys.stderr)
        return 2
    if args.cmd == "doctor":
        return cmd_doctor(args, ctx)
    if args.cmd == "owners":
        return cmd_owners(args, ctx)
    text = _read_input(args)
    if not text.strip():
        print("guardian: no input. Pass ticket text, a feature description or a diff (or pipe it on stdin).",
              file=sys.stderr)
        return 2
    return {"reuse": cmd_reuse, "history": cmd_history, "blueprint": cmd_blueprint}[args.cmd](args, ctx, text)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
