import pytest

from guardian_kit import history
from guardian_kit.text import build_query


def search(ctx, text, **kw):
    prs, _ = history.load_prs(ctx)
    return history.search(prs, build_query(text), **kw)


def test_loads_every_export_shape_and_reports_broken_files(ctx):
    prs, warnings = history.load_prs(ctx)
    assert {p.number for p in prs} == {"101", "142", "155", "160", "7"}
    states = {p.number: p.state for p in prs}
    assert states == {"101": "merged", "142": "rejected", "155": "rejected", "160": "merged", "7": "merged"}
    assert any("broken.json" in w for w in warnings)
    assert {p.repo for p in prs if p.number in {"101", "155"}} == {"payments-core"}  # from folder name


def test_rejected_pr_surfaces_with_reviewer_reason(ctx):
    m = {x.pr.number: x for x in search(ctx, "redact account digits in transaction logs")}
    assert "142" in m and m["142"].pr.state == "rejected"
    assert m["142"].reason_by == "asha"
    assert "duplicates mask_account_number" in m["142"].reason


def test_reason_from_plain_comment_on_rest_export(ctx):
    m = {x.pr.number: x for x in search(ctx, "retry payment gateway calls")}
    assert m["155"].reason_by == "marcus"
    assert "retry_with_backoff" in m["155"].reason


def test_related_files_boost_prs_that_touched_them(ctx):
    res = search(ctx, "settlement", related_files=["src/payments_core/calendar/business_days.py"])
    assert res[0].pr.number == "160"
    assert res[0].shared_files == ["src/payments_core/calendar/business_days.py"]


def test_state_filter_and_irrelevant_query(ctx):
    assert all(m.pr.state == "rejected" for m in search(ctx, "masking logs", state="rejected"))
    assert search(ctx, "dark mode toggle preferences") == []


def test_explicit_reason_field_wins():
    pr = history.normalize({"id": 9, "title": "x", "status": "declined", "rejection_reason": "Breaks policy SEC-4."})
    assert pr.state == "rejected"
    assert history.rejection_reason(pr)[0] == "Breaks policy SEC-4."


def test_authors_own_comment_is_not_the_reason():
    pr = history.normalize({
        "number": 1, "title": "t", "state": "closed", "author": "dev",
        "comments": [{"author": "dev", "body": "Closing, I will reuse the existing helper instead."},
                     {"author": "lead", "body": "Do not add a second cache; use the existing ttl_cache."}],
    })
    assert history.rejection_reason(pr)[1] == "lead"


def test_flat_export_file_names_the_repo(tmp_path):
    (tmp_path / "repos" / "locopy").mkdir(parents=True)
    (tmp_path / "prs").mkdir()
    (tmp_path / "prs" / "locopy.json").write_text('[{"number": 1, "title": "Add S3 upload", "state": "MERGED"}]')
    (tmp_path / "prs" / "misc.json").write_text('[{"number": 2, "title": "x", "state": "OPEN"}]')
    prs, _ = history.load_prs(tmp_path)
    assert {p.number: p.repo for p in prs} == {"1": "locopy", "2": ""}


@pytest.mark.parametrize("title, body, automated", [
    ("Update dependency pyarrow to v26", "", True),
    ("chore: bump version to 0.7.1", "", True),
    ("Changes by run-edgetest action", "Automated changes by edgetest", True),
    ("Bump urllib3 from 2.0 to 2.7", "", True),
    ("x", "This PR contains the following updates: | Package |", True),
    ("feat: add retry to the Redshift loader", "Wraps COPY in backoff.", False),
    ("Update docs for S3 upload", "", False),
])
def test_automated_prs_are_recognised_without_an_author(title, body, automated):
    pr = history.normalize({"number": 1, "title": title, "body": body, "state": "CLOSED"})
    assert history.is_automated(pr) is automated


def test_cla_and_ci_bots_are_never_reviewers():
    pr = history.normalize({"number": 1, "title": "t", "state": "closed", "author": "dev",
                            "comments": [{"author": "CLAassistant", "body": "Please sign the CLA before we can accept this."}]})
    assert history.rejection_reason(pr) == ("", "")
