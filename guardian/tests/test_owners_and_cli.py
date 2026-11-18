import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from guardian_kit import owners
from guardian_kit.blueprint import render_blueprint, run_blueprint
from guardian_kit.cli import main
from guardian_kit.context import list_repos
from guardian_kit.text import build_query

BIN = Path(__file__).resolve().parents[1] / "bin" / "guardian"
TODAY = dt.date(2026, 11, 18)


def test_owners_rank_recent_humans_and_skip_bots(ctx):
    repos = {r.name: r for r in list_repos(ctx)}
    found, notes = owners.find_owners(repos, [("payments-core", "src/payments_core/utils/masking.py")], today=TODAY)
    ranked = owners.rank(found)
    assert ranked[0].name == "Asha Rao" and ranked[0].commits == 2 and ranked[0].last == "2026-06-01"
    assert not any("dependabot" in o.name for o in ranked)
    assert notes == []


def test_codeowners_match():
    assert owners._codeowner_match("/src/payments_core/utils/", "src/payments_core/utils/masking.py")
    assert owners._codeowner_match("*.py", "a/b/c.py")
    assert not owners._codeowner_match("/docs/", "src/docs.py")


def test_blueprint_names_helper_pr_and_owner_and_fits_one_screen(ctx):
    ticket = "PAY-512: Mask customer account numbers in payment logs\n\nAudit found raw account numbers in logs."
    bp = run_blueprint(ctx, build_query(ticket), today=TODAY)
    md = render_blueprint(bp, "PAY-512: Mask customer account numbers in payment logs")
    assert bp["reuse"][0]["name"] == "mask_account_number"
    assert {p["number"] for p in bp["prs"]} >= {"101", "142"}
    assert bp["owners"][0]["name"] == "Asha Rao"
    assert "rejected #142" in bp["owners"][0]["evidence"]
    lines = md.splitlines()
    assert len(lines) <= 30 and max(map(len, lines)) <= 160


def test_cli_exit_codes(ctx, capsys, tmp_path):
    assert main(["reuse", "--context", str(tmp_path / "missing"), "x"]) == 2
    assert main(["reuse", "--context", str(ctx), "   "]) == 2
    assert main(["doctor", "--context", str(ctx)]) == 0
    assert main(["history", "--context", str(ctx), "--format", "json", "retry gateway"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out[out.index('{\n  "query"'):])["prs"][0]["number"] == "155"


def test_wrapper_script_reads_stdin(ctx):
    env = {**os.environ, "GUARDIAN_CONTEXT": str(ctx)}
    res = subprocess.run([str(BIN), "blueprint", "-"], input="Retry flaky gateway calls with backoff",
                         capture_output=True, text=True, env=env, check=False)
    assert res.returncode == 0, res.stderr
    assert "retry_with_backoff" in res.stdout and "### Who to ask" in res.stdout
