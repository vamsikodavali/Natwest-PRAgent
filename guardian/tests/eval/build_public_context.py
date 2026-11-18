"""Clone the public repos named in a case file at their pinned commits.

    python tests/eval/build_public_context.py tests/eval/public_cases.json .public-context

Re-running is cheap: repos already at the right commit are left alone. History
depth 300 is kept so owner ranking has real git authors to work with.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def ensure(name: str, url: str, sha: str, repos: Path) -> None:
    dest = repos / name
    if (dest / ".git").exists():
        try:
            if git("rev-parse", "HEAD", cwd=dest) == sha:
                print(f"  {name}: up to date at {sha[:10]}")
                return
        except subprocess.CalledProcessError:
            pass
    else:
        dest.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=dest)
        git("remote", "add", "origin", url, cwd=dest)
    print(f"  {name}: fetching {sha[:10]} from {url}")
    git("fetch", "-q", "--depth", "300", "origin", sha, cwd=dest)
    git("checkout", "-q", "--detach", sha, cwd=dest)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cases, out = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    spec = json.loads(cases.read_text(encoding="utf-8")).get("repos", {})
    if not spec:
        print(f"{cases} has no 'repos' section", file=sys.stderr)
        return 2
    (out / "prs").mkdir(parents=True, exist_ok=True)
    for name, r in spec.items():
        ensure(name, r["url"], r["sha"], out / "repos")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
