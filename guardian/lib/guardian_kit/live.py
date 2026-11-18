"""Render a `claude -p --output-format stream-json` run for a live audience.

Reads the event stream on stdin and does two things as it goes:

* prints one readable progress line per step in the terminal, and
* rewrites a Markdown file that VS Code's preview re-renders on every save,
  first as a "working..." page with the steps so far, then as the final result
  with a footer (time, model, cost).

Used by scripts/live.sh. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

ICONS = {"search": "🔎", "read": "📖", "grep": "🔍", "write": "📝", "gh": "🐙", "other": "⚙️"}


def _short(path: str) -> str:
    """Show repo-relative paths: .../context/repos/locopy/locopy/s3.py -> locopy/locopy/s3.py"""
    m = re.search(r"/repos/(.+)$", path) or re.search(r"/(prs/.+)$", path)
    if m:
        return m.group(1)
    return re.sub(r"^.*/guardian/", "", path)


def describe(tool: dict) -> tuple[str, str] | None:
    """(icon key, human sentence) for one tool call, or None to stay quiet."""
    name, inp = tool.get("name"), tool.get("input") or {}
    if name == "Bash":
        cmd = inp.get("command", "")
        m = re.search(r"\./bin/guardian (\w[\w-]*)", cmd)
        if m:
            what = {"blueprint": "Searching the code, past PRs and git history",
                    "reuse": "Searching the code for existing implementations",
                    "history": "Searching past pull requests",
                    "owners": "Looking up owners in git history"}.get(m.group(1), f"Running guardian {m.group(1)}")
            exp = re.search(r"--expand '([^']*)'", cmd)
            extra = f". AI-added search terms: *{exp.group(1)[:140]}*" if exp else ""
            return "search", what + extra
        if "gh pr comment" in cmd:
            return "gh", "Posting the review as a comment on the pull request"
        if "gh pr diff" in cmd or "curl -sL" in cmd:
            return "gh", "Fetching the pull request's changes from GitHub"
        if cmd.lstrip().startswith("gh auth"):
            return "gh", "Checking the GitHub login"
        return None
    if name == "Read":
        p = _short(inp.get("file_path", ""))
        if p.endswith("SKILL.md"):
            return None
        off, lim = inp.get("offset"), inp.get("limit")
        rng = f" (lines {off}-{off + lim})" if off and lim else ""
        if p.endswith(".diff"):
            what = "Reading the pull request's changes"
        elif p == "rules.md" or p.startswith("data/"):
            what = "Checking the rules and policies"
        elif p.startswith("prs/"):
            what = "Checking the past-PR record"
        else:
            what = "Reading the code to verify it"
        return "read", f"{what}: `{p}`{rng}"
    if name == "Grep":
        pat = str(inp.get("pattern", ""))[:60]
        return "grep", f"Double-checking with a search for `{pat}`"
    if name in ("Write", "Edit"):
        return "write", f"Writing `{_short(inp.get('file_path', ''))}`"
    return None


def _write(path: Path, text: str) -> None:
    """Rewrite the file in place.

    VS Code's Markdown preview follows a file by identity: an atomic
    write-to-temp-then-rename looks like "deleted, then a new file", and the
    preview can go blank or stop updating. One in-place write per update keeps it
    attached; the preview debounces, so it never shows a half-written page.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()


def run(stream, out: Path, title: str, subject: str, model: str, echo=print, label: str = "Ticket",
        prefix: str = "") -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    steps: list[str] = []

    def page(body: str) -> str:
        section = f"# {title}\n\n> **{label}:** {subject}\n\n{body}\n"
        return f"{prefix.rstrip()}\n\n---\n\n{section}" if prefix.strip() else section

    lock = threading.Lock()
    done = threading.Event()

    def working() -> None:
        lines = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) or "_Claude is reading the skill and planning…_"
        with lock:
            if not done.is_set():
                _write(out, page(f"## ⏳ Working… {time.time() - start:.0f}s\n\n{lines}"))

    def heartbeat() -> None:  # keep the preview visibly alive between steps
        while not done.wait(2.0):
            working()

    working()
    threading.Thread(target=heartbeat, daemon=True).start()
    echo(f"⏳ {title}: {subject[:90]}")
    result, cost, failed = None, None, None
    written: list[str] = []  # files the skill wrote (pr-review saves its comment under out/)
    for raw in stream:
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                if block.get("name") in ("Write", "Edit"):
                    written.append((block.get("input") or {}).get("file_path", ""))
                d = describe(block)
                if d:
                    icon, text = ICONS[d[0]], d[1]
                    steps.append(f"{icon} {text}")
                    echo(f"  {time.time() - start:5.0f}s  {icon} {text.replace('`', '').replace(': *', ': ').rstrip('*')}")
                    working()
        elif ev.get("type") == "result":
            result, cost = ev.get("result") or "", ev.get("total_cost_usd")
            if ev.get("subtype") != "success" or ev.get("is_error"):
                failed = ev.get("subtype") or "error"

    with lock:
        done.set()
    secs = time.time() - start
    if result is None:
        _write(out, page("## ❌ The run ended without a result\n\nCheck that `claude` is logged in, or re-run with `--offline`."))
        echo("❌ no result (is claude logged in?)")
        return 1
    review = next((Path(p) for p in reversed(written) if "/out/review-" in p or p.startswith("out/review-")), None)
    if review and review.is_file():
        # show the comment exactly as posted on the PR, with the alert banner (if any) on top
        alert = "\n".join(line for line in result.splitlines() if "OPENHANDS ALERT" in line)
        result = (f"> {alert.strip()}\n\n" if alert else "") + review.read_text(encoding="utf-8")
    footer = f"\n\n---\n<sub>Generated live by OpenHands in {secs:.0f}s · {model}"
    footer += f" · ${cost:.2f}" if cost is not None else ""
    footer += f" · {len(steps)} verification steps · every line cites a file, a PR or git history</sub>"
    _write(out, page(result.strip() + footer))
    echo(f"✅ done in {secs:.0f}s" + (f", ${cost:.2f}" if cost is not None else "") + f" → {out}")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="guardian live")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="💡 Code recommendation")
    ap.add_argument("--subject", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--label", default="Ticket")
    ap.add_argument("--prefix-file", help="keep this Markdown above the live section (earlier results)")
    a = ap.parse_args(argv)
    return run(sys.stdin, Path(a.out), a.title, a.subject, a.model, echo=lambda s: print(s, flush=True), label=a.label,
               prefix=Path(a.prefix_file).read_text(encoding="utf-8") if a.prefix_file else "")
