import json

from guardian_kit import history, importer
from guardian_kit.cli import main


def _w(p, data):
    p.write_text(json.dumps(data))
    return p


def test_rest_import_keeps_author_and_conversation_reasons(tmp_path):
    pulls = _w(tmp_path / "p.json", [
        {"number": 7, "title": "New redactor", "body": "b", "state": "closed", "merged_at": None,
         "user": {"login": "dev"}, "url": "https://api/pulls/7", "html_url": "https://gh/pull/7"},
        {"number": 8, "title": "Bump x", "body": "", "state": "closed", "merged_at": "2026-01-01",
         "user": {"login": "renovate[bot]"}, "url": "https://api/pulls/8", "html_url": "https://gh/pull/8"},
    ])
    inline = _w(tmp_path / "c.json", [{"pull_request_url": "https://api/pulls/7", "user": {"login": "lead"},
                                        "body": "nit", "path": "a.py", "created_at": "2026-01-01"}])
    convo = _w(tmp_path / "i.json", [{"issue_url": "https://api/issues/7", "user": {"login": "lead"},
                                       "body": "Closing: duplicates mask_account_number, reuse it instead.",
                                       "created_at": "2026-01-02"}])
    prs = importer.from_rest(pulls, inline, [convo])
    assert prs[0]["state"] == "CLOSED" and prs[0]["author"]["login"] == "dev"
    assert [c["body"] for c in prs[0]["comments"]] == ["nit", "Closing: duplicates mask_account_number, reuse it instead."]
    pr = history.normalize(prs[0])
    assert history.rejection_reason(pr) == ("Closing: duplicates mask_account_number, reuse it instead.", "lead")
    assert history.is_automated(history.normalize(prs[1]))


def test_api_errors_fail_loudly(tmp_path, capsys):
    bad = _w(tmp_path / "p.json", {"message": "API rate limit exceeded"})
    ok = _w(tmp_path / "c.json", [])
    out = tmp_path / "prs" / "r.json"
    assert main(["import-prs", "--pulls", str(bad), "--review-comments", str(ok), "-o", str(out)]) == 1
    assert "rate limit" in capsys.readouterr().err and not out.exists()
    assert main(["import-prs", "-o", str(out)]) == 2


def test_gh_export_passes_through(tmp_path, capsys):
    src = _w(tmp_path / "gh.json", [{"number": 1, "title": "t", "state": "MERGED", "author": {"login": "a"}}])
    out = tmp_path / "out.json"
    assert main(["import-prs", "--gh", str(src), "-o", str(out)]) == 0
    assert capsys.readouterr().out.strip() == "1" and json.loads(out.read_text())[0]["number"] == 1
