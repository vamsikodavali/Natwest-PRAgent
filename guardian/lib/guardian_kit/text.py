"""Turning tickets, diffs and code into comparable search terms.

Every term is reduced to a stem so that "masking", "masked" and "masks" meet.
Terms belong to *concepts*: a query word plus its synonyms form one concept,
which lets scoring reward candidates that cover several ideas in the ticket
instead of repeating one word many times.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_CODE_IDENT_RE = re.compile(r"\b(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]+_[A-Za-z0-9_]+)\b")

STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "could", "did", "do", "does", "doing", "done", "for", "from", "had", "has", "have", "having", "he", "her", "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "also", "any", "each", "every", "all", "both", "few", "many", "much", "via", "per", "across", "within", "without", "about", "above", "after", "again", "against", "before", "below", "between", "during", "further", "because", "let", "lets", "get", "gets", "got", "make", "makes", "made", "use", "uses", "used", "using", "need", "needs", "needed", "want", "wants", "wanted", "able", "like", "new", "add", "adds", "added", "adding", "implement", "implementing", "implemented", "implementation", "create", "creates", "creating", "support", "supports", "supported", "feature", "features", "ticket", "story", "task", "please", "ensure", "allow", "allows", "allowing", "user", "users", "developer", "developers", "someone", "something", "thing", "things", "way", "ways", "currently", "existing", "exist", "exists", "already", "instead", "etc", "eg", "ie", "e", "g", "one", "two", "first", "second", "must", "may", "might", "shall", "should", "true", "false", "null", "none", "self", "this", "cls", "return", "returns", "arg", "args", "kwargs", "str", "int", "bool", "void", "public", "private", "protected", "static", "final", "const", "var", "function", "def", "class", "import", "from", "export", "default", "async", "await", "new"]
)
# Words tickets are full of that never name what the code does.
TICKET_FILLER = frozenset(
    ["appear", "appears", "appeared", "appearing", "found", "full", "fully", "issue", "issues", "bug", "bugs", "problem", "problems", "fix", "fixes", "fixed", "fixing", "work", "works", "worked", "still", "see", "seen", "today", "going", "sure", "acceptance", "criteria", "given", "scenario", "because", "currently", "right", "wrong", "correct", "correctly", "properly", "instead", "happen", "happens", "happening", "seems", "team", "teams", "customer-facing", "asap", "urgent", "priority", "sprint", "jira", "story", "points", "estimate", "done", "definition", "bit", "bits", "keep", "keeps", "kept", "lot", "lots", "little", "whenever"]
)
STOPWORDS = STOPWORDS | TICKET_FILLER

# Each group is one idea. Stems are computed at import time so callers can pass
# any surface form. Keep groups tight: a loose synonym produces noisy matches.
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("mask", "redact", "obfuscate", "anonymize", "anonymise", "scrub", "conceal", "hide", "censor"),
    ("pii", "personal", "sensitive", "gdpr", "confidential"),
    ("retry", "backoff", "reattempt", "resilience", "resilient"),
    ("validate", "validation", "validator", "verify", "check", "valid", "invalid"),
    ("sanitize", "sanitise", "clean", "escape", "normalize", "normalise"),
    ("email", "mail", "smtp"),
    ("notify", "notification", "alert", "message"),
    ("currency", "money", "monetary", "amount", "price", "cash"),
    ("fx", "exchange", "conversion", "rate"),
    ("format", "formatter", "render", "pretty", "display", "humanize", "humanise"),
    ("iban", "bic", "swift", "sortcode"),
    ("account", "acct"),
    ("card", "pan"),
    ("date", "datetime", "timestamp", "calendar"),
    ("business", "working", "weekday"),
    ("holiday", "bankholiday"),
    ("cache", "memoize", "memoise", "memo", "ttl"),
    ("log", "logger", "logging"),
    ("audit", "trail"),
    ("encrypt", "decrypt", "cipher", "crypto", "encryption"),
    ("hash", "digest", "hmac", "checksum", "signature", "sign"),
    ("throttle", "ratelimit", "ratelimiter", "quota"),
    ("paginate", "pagination", "page", "cursor"),
    ("parse", "parser", "deserialize", "deserialise", "decode"),
    ("serialize", "serialise", "encode", "marshal"),
    ("auth", "authenticate", "authentication", "login", "signin"),
    ("token", "jwt", "bearer"),
    ("oauth", "oidc", "sso"),
    ("permission", "authorize", "authorise", "authorization", "rbac", "role", "acl"),
    ("http", "request", "fetch", "rest", "endpoint"),
    ("client", "sdk", "wrapper"),
    ("config", "configuration", "setting", "settings", "env", "environment"),
    ("secret", "credential", "password", "apikey", "vault"),
    ("convert", "converter", "transform", "map", "mapper"),
    ("customer", "payee", "payer", "holder"),
    ("transaction", "payment", "transfer", "txn", "remittance"),
    ("upload", "storage", "bucket", "blob", "s3"),
    ("error", "exception", "failure", "fault"),
    ("idempotency", "idempotent", "dedup", "deduplicate", "duplicate"),
    ("schedule", "scheduler", "cron", "job"),
    ("queue", "kafka", "topic", "consumer", "producer", "publish", "subscribe"),
    ("metric", "metrics", "telemetry", "monitor", "monitoring", "trace", "tracing"),
    ("feature flag", "flag", "toggle"),
    ("csv", "spreadsheet", "export"),
    ("pdf", "statement", "document"),
    ("phone", "mobile", "msisdn"),
    ("address", "postcode", "zipcode", "postal"),
    ("uuid", "guid", "identifier", "id"),
    ("timeout", "deadline"),
    ("health", "healthcheck", "liveness", "readiness"),
    ("fraud", "risk", "suspicious", "aml"),
    ("loan", "mortgage", "credit", "lending"),
    ("interest", "apr", "apy"),
    ("tax", "vat"),
    ("translate", "i18n", "locale", "localize", "localise"),
)


def stem(word: str) -> str:
    """Light suffix stripping. Deliberately conservative: false merges hurt precision."""
    w = word.lower()
    if len(w) <= 3 or w.isdigit():
        return w
    for suffix, repl in (
        ("ization", "ize"),
        ("isation", "ize"),
        ("ational", "ate"),
        ("ations", "ate"),
        ("ation", "ate"),
        ("ators", "ate"),
        ("ator", "ate"),
        ("ities", "ity"),
        ("ies", "y"),
        ("sses", "ss"),
        ("ises", "ize"),
        ("izes", "ize"),
        ("ised", "ize"),
        ("ized", "ize"),
        ("ising", "ize"),
        ("izing", "ize"),
        ("ise", "ize"),
        ("ings", ""),
        ("ing", ""),
        ("ers", "er"),
        ("ed", ""),
        ("s", ""),
    ):
        if suffix == "s" and (w.endswith("ss") or w.endswith("us") or w.endswith("is")):
            continue
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: len(w) - len(suffix)] + repl
            break
    # "retried" -> "retri" -> "retry"
    if w.endswith("i") and len(w) > 4:
        w = w[:-1] + "y"
    # "formatter" -> "formatt", "logger" -> "logg"
    if w.endswith("er") and len(w) > 5:
        w = w[:-2]
    # collapse doubled consonant left by suffix stripping: "logg" -> "log"
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]
    # "date"/"dates" -> "dat", "cache"/"caches" -> "cach"
    if w.endswith("e") and len(w) >= 4:
        w = w[:-1]
    return w


def split_identifier(token: str) -> list[str]:
    """``maskAccountNumber`` / ``mask_account_number`` -> ``["mask", "account", "number"]``."""
    parts: list[str] = []
    for chunk in re.split(r"[_\-\.\s/]+", token):
        if not chunk:
            continue
        parts.extend(p.lower() for p in _CAMEL_RE.findall(chunk))
    return parts


def tokens(text: str) -> list[str]:
    """All identifier fragments in ``text``, lowercased, not yet filtered or stemmed."""
    out: list[str] = []
    for ident in _IDENT_RE.findall(text):
        out.extend(split_identifier(ident))
    return out


def stems(text: str) -> list[str]:
    """Filtered, stemmed tokens of ``text`` (order kept, duplicates kept)."""
    return [stem(t) for t in tokens(text) if len(t) > 1 and t not in STOPWORDS]


def stem_set(text: str) -> set[str]:
    return set(stems(text))


_SYNONYMS: dict[str, frozenset[str]] = {}
for _group in _SYNONYM_GROUPS:
    _stems = frozenset(stem(w) for g in _group for w in split_identifier(g) if w not in STOPWORDS)
    for _s in _stems:
        _SYNONYMS[_s] = _SYNONYMS.get(_s, frozenset()) | _stems


def synonyms(term_stem: str) -> frozenset[str]:
    return _SYNONYMS.get(term_stem, frozenset())


@dataclass
class Query:
    """A weighted bag of stems grouped into concepts.

    ``terms`` maps stem -> (concept id, weight). ``identifiers`` holds exact code
    identifiers seen in the input (e.g. ``maskPan``) for exact-name bonuses.
    """

    raw: str
    terms: dict[str, tuple[int, float]] = field(default_factory=dict)
    concepts: dict[int, str] = field(default_factory=dict)
    identifiers: set[str] = field(default_factory=set)
    diff_files: list[str] = field(default_factory=list)
    is_diff: bool = False
    hints: set[int] = field(default_factory=set)  # concepts that came only from --expand
    expanded: list[str] = field(default_factory=list)

    @property
    def concept_count(self) -> int:
        """Concepts the ticket itself states. Hint concepts add score but never dilute coverage."""
        return len(self.concepts) - len(self.hints)

    def primary_hits(self, concept_ids) -> int:
        return sum(1 for c in concept_ids if c not in self.hints)

    def concept_of(self, term_stem: str) -> int | None:
        hit = self.terms.get(term_stem)
        return hit[0] if hit else None

    def label(self) -> str:
        return ", ".join(self.concepts[c] for c in sorted(self.concepts))


_TICKET_ID = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
DIFF_MARKERS = re.compile(r"^(diff --git |@@ |\+\+\+ |--- a/)", re.M)


def looks_like_diff(text: str) -> bool:
    return len(DIFF_MARKERS.findall(text)) >= 2


def _diff_parts(text: str) -> tuple[str, list[str]]:
    """Return (added text, touched file paths) from a unified diff."""
    added: list[str] = []
    files: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path != "/dev/null":
                files.append(path)
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return "\n".join(added), files


_DEF_NAME_RE = re.compile(
    r"\b(?:def|function|func|fn|fun|class|interface|struct|record)\s+([A-Za-z_]\w*)"
    r"|\b(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:\(|function)"
)


def build_query(text: str, max_concepts: int = 12) -> Query:
    """Parse a ticket, feature description or unified diff into a :class:`Query`."""
    q = Query(raw=text)
    body = _TICKET_ID.sub(" ", text)  # PAY-512, JIRA-77: identifiers, not intent
    weights: dict[str, float] = {}

    if looks_like_diff(text):
        q.is_diff = True
        body, q.diff_files = _diff_parts(text)
        # names defined by the diff say most about intent
        for m in _DEF_NAME_RE.finditer(body):
            name = m.group(1) or m.group(2)
            q.identifiers.add(name)
            for s in stems(name):
                weights[s] = weights.get(s, 0) + 2.0
        for path in q.diff_files:
            for s in stems(path.rsplit(".", 1)[0]):
                weights[s] = weights.get(s, 0) + 0.5

    for ident in _CODE_IDENT_RE.findall(body):
        q.identifiers.add(ident)
    for ident in re.findall(r"`([A-Za-z_][\w.]*)\(?\)?`", body):
        q.identifiers.add(ident.split(".")[-1])

    for s in stems(body):
        weights[s] = weights.get(s, 0) + 1.0

    # Rank stems by frequency-dampened weight and keep the strongest concepts.
    ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
    concept_id = 0
    for s, w in ranked:
        if s in q.terms:
            continue
        if concept_id >= max_concepts:
            break
        base = 1.0 + 0.25 * min(w - 1.0, 4.0)  # repeated words matter, but sub-linearly
        q.terms[s] = (concept_id, base)
        q.concepts[concept_id] = s
        for syn in synonyms(s):
            if syn not in q.terms:
                q.terms[syn] = (concept_id, base * 0.7)
        concept_id += 1
    return q


HINT_WEIGHT = 0.6
LINKED_WEIGHT = 0.85


def expand_query(q: Query, spec: str) -> Query:
    """Merge model-suggested search terms into ``q``.

    ``spec`` is ``;``-separated groups. ``word=alt1,alt2`` links the alternatives to
    the ticket concept ``word`` (so they count toward coverage, like a synonym). A
    bare term becomes a low-weight *hint* concept. Terms that look like code
    identifiers (``maskPan``, ``redact_pii``) also get an exact-name bonus::

        obscure=mask,redact,hide; account=acct,iban; maskAccountNumber, redact_pii
    """
    if not spec or not spec.strip():
        return q
    next_id = max(q.concepts, default=-1) + 1
    for group in re.split(r"[;\n]+", spec):
        group = group.strip()
        if not group:
            continue
        key, sep, rest = group.partition("=")
        items = [i.strip() for i in (rest if sep else group).split(",") if i.strip()]
        target = None
        if sep:
            for ks in stems(key):
                target = q.concept_of(ks)
                if target is not None:
                    break
        for item in items:
            q.expanded.append(item)
            if _IDENT_RE.fullmatch(item) and len(split_identifier(item)) >= 2:
                q.identifiers.add(item)
            item_stems = [t for t in stems(item) if t not in q.terms]
            if not item_stems:
                continue
            if target is not None:
                weight = q.terms[q.concepts[target]][1] * LINKED_WEIGHT
                for t in item_stems:
                    q.terms[t] = (target, weight)
                continue
            if sep:
                # "keep out=hide,mask": the ticket states this idea in words we filter
                # out, so the alternatives become one full concept of their own.
                target = next_id
                q.concepts[next_id] = item_stems[0]
                for t in item_stems:
                    q.terms[t] = (target, LINKED_WEIGHT)
                    for syn in synonyms(t):
                        q.terms.setdefault(syn, (target, LINKED_WEIGHT * 0.7))
                next_id += 1
                continue
            # an unlinked guess is one hint concept (its words reinforce each other)
            q.concepts[next_id] = item_stems[0]
            q.hints.add(next_id)
            for t in item_stems:
                q.terms[t] = (next_id, HINT_WEIGHT)
                for syn in synonyms(t):
                    q.terms.setdefault(syn, (next_id, HINT_WEIGHT * 0.7))
            next_id += 1
    return q
