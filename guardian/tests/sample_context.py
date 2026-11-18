"""Builds a small but realistic context/ folder for tests and offline demos.

    python tests/sample_context.py /path/to/out    # then GUARDIAN_CONTEXT=/path/to/out

Two repos with real git history (fixed authors and dates), a file/folder
breakdown doc, and PR exports in three different JSON shapes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

PAYMENTS_FILES = {
    "src/payments_core/__init__.py": "",
    "src/payments_core/utils/masking.py": '''
        """Helpers for keeping customer identifiers out of logs and screens."""

        import re

        _DIGITS = re.compile(r"\\d")


        def mask_account_number(value: str, visible: int = 4, mask_char: str = "*") -> str:
            """Replace all but the last ``visible`` digits of an account or card number.

            Safe to call on already-masked or empty values. Use before logging.
            """
            if not value:
                return value
            digits = [m.start() for m in _DIGITS.finditer(value)]
            hide = digits[:-visible] if visible else digits
            chars = list(value)
            for i in hide:
                chars[i] = mask_char
            return "".join(chars)


        def mask_email(address: str) -> str:
            """j***@example.com style masking for email addresses."""
            local, _, domain = address.partition("@")
            return (local[:1] + "***@" + domain) if domain else "***"
    ''',
    "src/payments_core/utils/fmt.py": '''
        from decimal import Decimal, ROUND_HALF_EVEN


        def amt_str(amount: Decimal, ccy: str = "GBP") -> str:
            q = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            symbol = {"GBP": "£", "EUR": "€", "USD": "$"}.get(ccy, ccy + " ")
            return f"{symbol}{q:,}"
    ''',
    "src/payments_core/utils/retry.py": '''
        import random
        import time


        def retry_with_backoff(fn, attempts: int = 5, base_delay: float = 0.2, max_delay: float = 5.0):
            """Call ``fn`` until it succeeds, sleeping with exponential backoff and jitter."""
            for attempt in range(attempts):
                try:
                    return fn()
                except Exception:
                    if attempt == attempts - 1:
                        raise
                    time.sleep(min(max_delay, base_delay * 2 ** attempt) * (0.5 + random.random()))
    ''',
    "src/payments_core/validation/iban.py": '''
        def is_valid_iban(iban: str) -> bool:
            """Validate an IBAN using the ISO 13616 mod-97 checksum."""
            s = iban.replace(" ", "").upper()
            if len(s) < 15 or not s.isalnum():
                return False
            rearranged = s[4:] + s[:4]
            return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


        def is_valid_sort_code(code: str) -> bool:
            """UK sort codes: six digits, optionally written as 12-34-56."""
            digits = code.replace("-", "").replace(" ", "")
            return len(digits) == 6 and digits.isdigit()
    ''',
    "src/payments_core/payments/service.py": '''
        import logging

        from payments_core.utils.masking import mask_account_number
        from payments_core.utils.retry import retry_with_backoff

        log = logging.getLogger(__name__)


        class PaymentService:
            def __init__(self, gateway):
                self.gateway = gateway

            def submit(self, payment):
                log.info("submitting payment from %s", mask_account_number(payment.debtor_account))
                return retry_with_backoff(lambda: self.gateway.send(payment))

            def refund(self, payment_id: str):
                return self.gateway.refund(payment_id)
    ''',
    "src/payments_core/calendar/business_days.py": '''
        import datetime as dt

        UK_BANK_HOLIDAYS = {dt.date(2026, 12, 25), dt.date(2026, 12, 28)}


        def add_business_days(start: dt.date, days: int, holidays=UK_BANK_HOLIDAYS) -> dt.date:
            """Add working days, skipping weekends and UK bank holidays (settlement dates)."""
            d = start
            while days > 0:
                d += dt.timedelta(days=1)
                if d.weekday() < 5 and d not in holidays:
                    days -= 1
            return d
    ''',
    "tests/test_masking.py": '''
        from payments_core.utils.masking import mask_account_number


        def test_masks_all_but_last_four():
            assert mask_account_number("12345678") == "****5678"
    ''',
}

WEB_FILES = {
    "src/lib/http/fetchWithRetry.ts": '''
        /**
         * fetch() wrapper that retries 5xx and network errors with exponential backoff.
         */
        export async function fetchWithRetry(url: string, init: RequestInit = {}, retries = 3): Promise<Response> {
          for (let i = 0; ; i++) {
            try {
              const res = await fetch(url, init);
              if (res.status < 500 || i >= retries) return res;
            } catch (e) {
              if (i >= retries) throw e;
            }
            await new Promise((r) => setTimeout(r, 200 * 2 ** i));
          }
        }
    ''',
    "src/lib/format/money.ts": '''
        // Format a minor-unit amount (pence) as a localised currency string.
        export const formatMoney = (pence: number, currency = "GBP", locale = "en-GB"): string =>
          new Intl.NumberFormat(locale, { style: "currency", currency }).format(pence / 100);
    ''',
    "src/components/AccountCard.tsx": '''
        import { formatMoney } from "../lib/format/money";

        export function AccountCard({ name, balance }: { name: string; balance: number }) {
          return <div>{name}: {formatMoney(balance)}</div>;
        }
    ''',
}

PAYMENTS_MAP = """
# payments-core: file and folder breakdown

| Path | What it does |
|---|---|
| `src/payments_core/utils/` | Shared helpers used by every service |
| `src/payments_core/utils/masking.py` | Masks account numbers, card PANs and emails so PII never reaches logs |
| `src/payments_core/utils/fmt.py` | Formats money amounts as currency strings (`amt_str`) for statements and emails |
| `src/payments_core/utils/retry.py` | Retry with exponential backoff for flaky downstream calls |
| `src/payments_core/validation/` | IBAN and UK sort code validation |
| `src/payments_core/calendar/business_days.py` | Settlement date maths: working days, UK bank holidays |
| `src/payments_core/payments/` | Payment submission and refunds |
"""

PRS_GH = [
    {
        "number": 101, "title": "Add account number masking helper", "state": "MERGED",
        "author": {"login": "asha"}, "mergedAt": "2025-03-04T10:00:00Z",
        "body": "Adds mask_account_number so we stop logging raw account numbers.",
        "files": [{"path": "src/payments_core/utils/masking.py"}, {"path": "tests/test_masking.py"}],
        "reviews": [{"author": {"login": "marcus"}, "state": "APPROVED", "body": "LGTM"}],
        "url": "https://git.example/payments-core/pull/101",
    },
    {
        "number": 142, "title": "New PII redactor for transaction logs", "state": "CLOSED",
        "author": {"login": "devon"},
        "body": "Introduces a PiiRedactor class that hides customer account digits in log lines.",
        "files": [{"path": "src/payments_core/logging/pii_redactor.py"}],
        "reviews": [
            {"author": {"login": "devon"}, "state": "COMMENTED", "body": "Ready for review."},
            {"author": {"login": "asha"}, "state": "CHANGES_REQUESTED",
             "body": "This duplicates mask_account_number in utils/masking.py. Please reuse that instead of a second redactor. Closing."},
        ],
    },
]
PRS_REST = {
    "pull_requests": [
        {
            "number": 155, "title": "Retry payment gateway calls", "state": "closed", "merged": False,
            "user": {"login": "priya"},
            "body": "Wrap gateway.send in a hand-rolled while loop with time.sleep(1).",
            "files": ["src/payments_core/payments/service.py"],
            "comments": [{"user": {"login": "marcus"},
                          "body": "We already have retry_with_backoff. A fixed 1s sleep hammers the gateway during incidents. Rejecting."}],
        },
        {
            "number": 160, "title": "Settlement date calculation for faster payments", "state": "closed",
            "merged_at": "2025-08-01T09:00:00Z", "user": {"login": "marcus"},
            "body": "add_business_days skips weekends and bank holidays.",
            "files": ["src/payments_core/calendar/business_days.py"],
        },
    ]
}
PRS_FLAT = {"number": "7", "title": "Upgrade React to 18", "status": "merged", "repo": "web-banking",
            "description": "Dependency bump.", "files_changed": ["package.json"]}

COMMITS = {
    "payments-core": [
        ("Asha Rao", "asha@bank.example", "2025-03-04T10:00:00", ["src/payments_core/utils/masking.py", "tests/test_masking.py", "src/payments_core/__init__.py"]),
        ("Marcus Lee", "marcus@bank.example", "2025-04-10T10:00:00", ["src/payments_core/utils/retry.py", "src/payments_core/payments/service.py"]),
        ("Asha Rao", "asha@bank.example", "2026-06-01T10:00:00", ["src/payments_core/utils/masking.py:touch"]),
        ("Marcus Lee", "marcus@bank.example", "2025-08-01T09:00:00", ["src/payments_core/calendar/business_days.py", "src/payments_core/validation/iban.py", "src/payments_core/utils/fmt.py"]),
        ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com", "2026-07-01T10:00:00", ["src/payments_core/utils/masking.py:touch"]),
    ],
    "web-banking": [
        ("Priya Shah", "priya@bank.example", "2025-11-11T10:00:00", list(WEB_FILES)),
    ],
}


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _commit_history(repo: Path, files: dict[str, str], commits) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "commit.gpgsign", "false")
    for name, email, date, paths in commits:
        for p in paths:
            if p.endswith(":touch"):
                f = repo / p[:-6]
                f.write_text(f.read_text() + "\n", encoding="utf-8")
                _git(repo, "add", p[:-6])
            else:
                _write(repo, {p: files[p]})
                _git(repo, "add", p)
        env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": date}
        _git(repo, "commit", "-q", "-m", f"change by {name}", env=env)


def build(out: Path) -> Path:
    repos = out / "repos"
    pay = repos / "payments-core"
    web = repos / "web-banking"
    pay.mkdir(parents=True, exist_ok=True)
    web.mkdir(parents=True, exist_ok=True)
    _commit_history(pay, PAYMENTS_FILES, COMMITS["payments-core"])
    _commit_history(web, WEB_FILES, COMMITS["web-banking"])
    (repos / "payments-core.md").write_text(PAYMENTS_MAP.lstrip(), encoding="utf-8")

    prs = out / "prs"
    (prs / "payments-core").mkdir(parents=True, exist_ok=True)
    (prs / "payments-core" / "gh-export.json").write_text(json.dumps(PRS_GH, indent=1), encoding="utf-8")
    (prs / "payments-core" / "rest-export.json").write_text(json.dumps(PRS_REST, indent=1), encoding="utf-8")
    (prs / "web-7.json").write_text(json.dumps(PRS_FLAT), encoding="utf-8")
    (prs / "broken.json").write_text("{not json", encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: sample_context.py <out-dir>")
    print(build(Path(sys.argv[1]).resolve()))
