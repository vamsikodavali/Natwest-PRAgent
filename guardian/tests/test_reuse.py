import pytest

from guardian_kit import reuse
from guardian_kit.code_index import SourceFile, extract_symbols
from guardian_kit.context import Repo
from guardian_kit.text import build_query


def top(ctx, text, **kw):
    cands, _ = reuse.search(ctx, build_query(text), **kw)
    return cands


@pytest.mark.parametrize(
    "ticket, expected",
    [
        ("Hide all but the last four digits of a customer account number before logging", "mask_account_number"),
        ("Redact card numbers in application logs", "mask_account_number"),
        ("Calls to the payment gateway fail intermittently, retry them", "retry_with_backoff"),
        ("Work out the settlement date skipping weekends and bank holidays", "add_business_days"),
        ("Check that the IBAN a customer typed is valid", "is_valid_iban"),
        # amt_str has no docstring and a cryptic name: only the breakdown doc can find it
        ("Show balances as pounds and pence on the statement email", "amt_str"),
        ("Format pence as a GBP currency string in the React account card", "formatMoney"),
        ("fetch wrapper that retries server errors", "fetchWithRetry"),
    ],
)
def test_described_in_words_finds_the_helper(ctx, ticket, expected):
    names = [c.symbol.name for c in top(ctx, ticket)]
    assert names and names[0] == expected, names


def test_unrelated_ticket_returns_nothing(ctx):
    assert top(ctx, "Add a dark mode toggle to the preferences screen") == []


def test_candidate_carries_call_site_and_import(ctx):
    c = top(ctx, "mask account number before logging")[0]
    assert c.call_sites and c.call_sites[0].startswith("src/payments_core/payments/service.py:")
    assert c.import_hint == "from payments_core.utils.masking import mask_account_number"
    assert c.symbol.end_line > c.symbol.line


def test_tests_are_excluded_by_default(ctx):
    assert all(not c.symbol.is_test for c in top(ctx, "masks all but last four", limit=10))


def test_same_file_hits_are_grouped_unless_both_are_strong(ctx):
    # both helpers answer the ticket: they get separate entries (grab-bag utils files)
    both = top(ctx, "validate IBAN and sort code bank details")
    assert {"is_valid_iban", "is_valid_sort_code"} <= {c.symbol.name for c in both}
    # a weaker same-file hit is folded into the lead entry instead of taking a slot
    lead = top(ctx, "mask customer account number digits before logging")[0]
    assert lead.symbol.name == "mask_account_number"
    assert "mask_email" in lead.siblings


def test_diff_that_reimplements_a_helper_points_to_it(ctx):
    diff = (
        "diff --git a/r.py b/r.py\n--- /dev/null\n+++ b/src/payments_core/payments/refunds.py\n@@ -0,0 +1,3 @@\n"
        "+def obscure_acct(num):\n+    # hide account digits before logging\n+    return '*' * (len(num) - 4) + num[-4:]\n"
    )
    assert top(ctx, diff)[0].symbol.name == "mask_account_number"


def test_repo_filter(ctx):
    assert all(c.symbol.repo == "web-banking" for c in top(ctx, "retry with backoff", repos=["web-banking"]))


@pytest.mark.parametrize(
    "lang, src, names",
    [
        ("java", "public class Masker {\n  /** Masks PANs. */\n  public static String maskPan(String pan) {\n    return pan;\n  }\n}\n", {"Masker", "maskPan"}),
        ("go", "// Retry calls f.\nfunc Retry(f func() error, n int) error {\n\treturn nil\n}\n", {"Retry"}),
        ("kotlin", "fun String.maskEmail(): String = this\n", {"maskEmail"}),
        ("js", "export const toPence = (x) => x * 100;\nconst y = compute(1);\n", {"toPence"}),
        ("rust", "pub fn redact(s: &str) -> String { s.into() }\n", {"redact"}),
    ],
)
def test_symbol_extraction_across_languages(tmp_path, lang, src, names):
    f = SourceFile(Repo("r", tmp_path), f"x.{lang}", lang, src)
    assert {s.name for s in extract_symbols(f)} == names


def test_java_doc_comment_is_captured(tmp_path):
    src = "class A {\n  /**\n   * Masks a card PAN.\n   */\n  public String maskPan(String p) { return p; }\n}\n"
    sym = next(s for s in extract_symbols(SourceFile(Repo("r", tmp_path), "A.java", "java", src)) if s.name == "maskPan")
    assert "Masks a card PAN" in sym.doc
    assert sym.parent == "A"


def test_java_interface_methods_are_indexed(tmp_path):
    src = (
        "public interface OwnerRepository extends JpaRepository<Owner, Integer> {\n"
        "  /** Owners whose last name starts with the given prefix. */\n"
        "  Page<Owner> findByLastNameStartingWith(String lastName, Pageable pageable);\n"
        "  List<PetType> findPetTypes();\n"
        "}\n"
        "class X { void run() {\n    return foo(bar);\n    throw new Oops(x);\n    helper(a, b);\n  }\n}\n"
    )
    syms = {s.name: s for s in extract_symbols(SourceFile(Repo("r", tmp_path), "O.java", "java", src))}
    assert {"findByLastNameStartingWith", "findPetTypes"} <= set(syms)
    assert syms["findByLastNameStartingWith"].parent == "OwnerRepository"
    assert "last name starts" in syms["findByLastNameStartingWith"].doc
    assert not {"foo", "Oops", "helper"} & set(syms)
