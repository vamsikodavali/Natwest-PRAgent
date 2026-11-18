import json

import pytest

from guardian_kit import evaluate
from guardian_kit.cli import main


def test_sample_eval_meets_the_quality_bar(ctx):
    cases = evaluate.load_cases(evaluate.Path(__file__).parent / "eval" / "sample_cases.json")
    _, summary = evaluate.run(ctx, cases)
    base, exp = summary["modes"]["baseline"], summary["modes"]["expanded"]
    assert base["recall@3"] >= 0.75
    assert exp["recall@3"] >= base["recall@3"]  # expansion must never make things worse overall
    assert exp["silent_on_negatives"] == 1.0
    assert exp["pr_recall"] == 1.0


def test_target_forms_match(ctx):
    from guardian_kit import reuse
    from guardian_kit.text import build_query

    c = reuse.search(ctx, build_query("mask account number before logging"))[0][0]
    for target in ("mask_account_number", "utils/masking.py", "utils/masking.py:mask_account_number",
                   "payments-core/src/payments_core/utils/masking.py:mask_account_number"):
        assert evaluate._matches(target, c), target
    assert not evaluate._matches("retry.py:mask_account_number", c)


def test_eval_cli_gate_and_bad_files(ctx, tmp_path, capsys):
    cases = tmp_path / "c.json"
    cases.write_text(json.dumps([{"id": "x", "ticket": "dark mode toggle", "expect": ["nope"]}]))
    assert main(["eval", "--context", str(ctx), str(cases), "--min-recall", "0.5"]) == 1
    cases.write_text(json.dumps([{"id": "x"}]))
    assert main(["eval", "--context", str(ctx), str(cases)]) == 2
    assert main(["eval", "--context", str(ctx), str(tmp_path / "missing.json")]) == 2


@pytest.mark.parametrize("bad", [[{"ticket": "t"}], {"cases": [{"ticket": "t", "negative": False}]}])
def test_cases_need_expectations(tmp_path, bad):
    f = tmp_path / "c.json"
    f.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        evaluate.load_cases(f)
