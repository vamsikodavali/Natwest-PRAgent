import pytest

from guardian_kit.text import build_query, looks_like_diff, split_identifier, stem


@pytest.mark.parametrize(
    "words",
    [
        ("masking", "masked", "masks", "mask"),
        ("retry", "retries", "retried"),
        ("logger", "logging", "log"),
        ("validate", "validation", "validator"),
        ("format", "formatter"),
        ("anonymise", "anonymization", "anonymize"),
        ("address", "addresses"),
        ("date", "dates"),
    ],
)
def test_inflections_share_a_stem(words):
    assert len({stem(w) for w in words}) == 1


def test_split_identifier_handles_camel_snake_and_acronyms():
    assert split_identifier("maskAccountNumber") == ["mask", "account", "number"]
    assert split_identifier("mask_account_number") == ["mask", "account", "number"]
    assert split_identifier("parseHTTPResponse") == ["parse", "http", "response"]


def test_query_expands_synonyms_into_the_same_concept():
    q = build_query("redact customer account numbers")
    assert q.concept_of("mask") == q.concept_of("redact")
    assert q.concept_count == 4  # redact, customer, account, number


def test_query_drops_ticket_filler():
    q = build_query("As a user I want to be able to add a new feature")
    assert q.concept_count == 0


def test_diff_input_uses_added_lines_and_defined_names():
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1,2 @@\n-old_stuff()\n+def obscure_acct(n):\n+    pass\n"
    assert looks_like_diff(diff)
    q = build_query(diff)
    assert q.is_diff and q.diff_files == ["a.py"]
    assert "obscure_acct" in q.identifiers
    assert q.concept_of(stem("old")) is None  # removed lines are ignored


def test_ticket_ids_and_filler_are_not_concepts():
    q = build_query("PAY-512: account numbers appear in full in logs, found by audit")
    assert "pay" not in q.concepts.values()
    assert not {"appear", "found", "full"} & set(q.concepts.values())


def test_expansion_links_alternatives_to_ticket_concepts():
    from guardian_kit.text import expand_query

    q = expand_query(build_query("make debtor account numbers unreadable"), "unreadable=mask,redact; maskPan, retry_call")
    unreadable = q.concept_of(stem("unreadable"))
    assert q.concept_of("mask") == unreadable  # linked: counts toward coverage
    assert {"maskPan", "retry_call"} <= q.identifiers  # exact-name guesses
    assert q.hints  # unlinked guesses become hint concepts
    assert q.concept_count == len(q.concepts) - len(q.hints)


def test_empty_expansion_is_a_no_op():
    from guardian_kit.text import expand_query

    a = build_query("mask account numbers")
    b = expand_query(build_query("mask account numbers"), "  ")
    assert a.terms == b.terms and not b.hints
