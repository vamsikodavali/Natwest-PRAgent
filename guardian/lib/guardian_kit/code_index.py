"""A light, language-agnostic symbol index over the cloned repositories.

Regex-based on purpose: it has to cope with any language a team uses, with no
build step and no parser dependencies. It finds function, method and type
definitions with their leading doc comment or docstring, which is what a
reuse search needs. Precision comes later, when Claude reads the candidate.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .context import Repo

CODE_EXT = {
    ".py": "python", ".pyi": "python",
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js", ".ts": "js", ".tsx": "js",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "java", ".cs": "java",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".c": "c", ".h": "c", ".cc": "c", ".cpp": "c", ".hpp": "c",
    ".sh": "shell", ".bash": "shell", ".sql": "sql", ".tf": "terraform",
}
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "out", ".venv", "venv",
    "env", "__pycache__", ".idea", ".vscode", ".gradle", "coverage", ".next", ".nuxt",
    "site-packages", ".mypy_cache", ".pytest_cache", ".tox", "bower_components", ".terraform",
    "generated", "__generated__", ".cache",
}
TEST_PATH = re.compile(r"(^|/)(tests?|spec|specs|__tests__|__mocks__|mocks?|fixtures?|testdata|e2e)(/|$)|(_test|\.test|\.spec|_spec|Test|Tests)\.\w+$|(^|/)test_[^/]+$")
MAX_FILE_BYTES = 512_000
MAX_FILES_PER_REPO = 25_000

_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "else", "do", "try", "with",
    "function", "constructor", "super", "this", "typeof", "sizeof", "elif", "except", "when",
    "match", "case", "throw", "await", "yield", "assert", "require", "import", "from", "main",
    "init", "__init__", "setUp", "tearDown", "toString", "equals", "hashCode", "get", "set",
}

_PY_DEF = re.compile(r"^(?P<ind>[ \t]*)(?:async[ \t]+)?def[ \t]+(?P<name>\w+)[ \t]*\((?P<sig>[^)]*)")
_PY_CLASS = re.compile(r"^(?P<ind>[ \t]*)class[ \t]+(?P<name>\w+)")
_GENERIC = [
    ("function", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\((?P<sig>[^)]*)")),
    ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:function\b[^(]*)?\((?P<sig>[^)]*)\)?\s*(?::[^=]*)?=?>?")),
    ("method", re.compile(r"^\s+(?:(?:public|private|protected|static|readonly|async|override|get|set)\s+)*(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\((?P<sig>[^)]*)\)\s*(?::\s*[^{;]+)?\{")),
    ("method", re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|private|protected|internal|static|final|abstract|synchronized|override|virtual|async|default|sealed|open|suspend|inline)\s+)+(?:<[^>]+>\s+)?[\w<>\[\],.?]+\s+(?P<name>\w+)\s*\((?P<sig>[^)]*)")),
    ("function", re.compile(r"\bfun\s+(?:<[^>]+>\s*)?(?:[\w.]+\.)?(?P<name>\w+)\s*\((?P<sig>[^)]*)")),
    ("function", re.compile(r"^func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)\s*(?:\[[^\]]*\])?\((?P<sig>[^)]*)")),
    ("function", re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(?P<name>\w+)\s*(?:<[^>]*>)?\s*\((?P<sig>[^)]*)")),
    ("function", re.compile(r"^\s*def\s+(?:self\.)?(?P<name>\w+[?!]?)\s*\(?(?P<sig>[^)\n]*)")),
    ("function", re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*function\s+(?P<name>\w+)\s*\((?P<sig>[^)]*)")),
    ("function", re.compile(r"^\s*(?:function\s+)?(?P<name>[A-Za-z_][\w-]*)\s*\(\)\s*\{")),
    ("type", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:(?:public|private|protected|internal|abstract|final|sealed|data|open|static|partial)\s+)*(?:class|interface|trait|struct|enum|record|object|type)\s+(?P<name>[A-Za-z_]\w*)")),
    ("resource", re.compile(r'^\s*(?:resource|module|data)\s+"(?P<name>[\w\-]+)"(?:\s+"(?P<sig>[\w\-]+)")?')),
    ("function", re.compile(r"^\s*create\s+(?:or\s+replace\s+)?(?:function|procedure|view)\s+(?P<name>[\w.]+)", re.I)),
]


# Body-less declarations: interface methods, abstract methods, Spring Data finders.
#   Page<Owner> findByLastNameStartingWith(String lastName, Pageable pageable);
_JAVA_ABSTRACT = re.compile(
    r"^\s+(?!(?:return|throw|new|else|yield|assert|await|super|this)\b)"
    r"(?:(?:public|protected|abstract|default|static|synchronized)\s+)*(?:<[^>]+>\s+)?"
    r"[\w.]+(?:<[^;()]*>)?(?:\[\])*\s+(?P<name>[a-z_]\w*)\s*\((?P<sig>[^)]*)\)\s*(?:throws\s+[\w.,\s]+)?;\s*$"
)


@dataclass
class Symbol:
    repo: str
    path: str  # repo-relative, forward slashes
    name: str
    kind: str
    line: int
    end_line: int
    signature: str
    doc: str
    is_test: bool
    parent: str | None = None
    name_stems: set[str] = field(default_factory=set)
    doc_stems: set[str] = field(default_factory=set)
    path_stems: set[str] = field(default_factory=set)
    map_stems: set[str] = field(default_factory=set)
    map_note: str = ""

    @property
    def location(self) -> str:
        return f"{self.repo}/{self.path}:{self.line}"


@dataclass
class SourceFile:
    repo: Repo
    relpath: str
    lang: str
    text: str

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


def iter_source_files(repo: Repo):
    count = 0
    for root, dirs, files in os.walk(repo.path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            lang = CODE_EXT.get(ext)
            if not lang or fname.endswith((".min.js", ".d.ts", ".bundle.js")):
                continue
            full = Path(root) / fname
            try:
                if full.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            count += 1
            if count > MAX_FILES_PER_REPO:
                return
            yield SourceFile(repo, full.relative_to(repo.path).as_posix(), lang, text)


def all_relpaths(repo: Repo) -> list[str]:
    out = []
    for root, dirs, files in os.walk(repo.path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            out.append((Path(root) / f).relative_to(repo.path).as_posix())
    return out


def _leading_comment(lines: list[str], idx: int) -> str:
    """Comment block directly above line ``idx`` (skipping decorators/annotations)."""
    out: list[str] = []
    i = idx - 1
    while i >= 0 and re.match(r"^\s*[@#]\[?\w", lines[i]) and not lines[i].lstrip().startswith("# "):
        i -= 1  # decorators, annotations, rust attributes
    in_block = False
    while i >= 0:
        s = lines[i].strip()
        if s.endswith("*/"):
            in_block = True
        if in_block or s.startswith(("//", "#", "*", "/*", "--", '"""')):
            out.append(re.sub(r"^(///?|#+|/\*\*?|\*/?|--)\s?", "", s).rstrip("*/ ").strip())
            if s.startswith("/*"):
                in_block = False
            i -= 1
            continue
        break
    return " ".join(reversed([o for o in out if o])).strip()


def _python_docstring(lines: list[str], idx: int) -> str:
    # skip to the end of a multi-line signature
    j = idx
    while j < len(lines) and not lines[j].rstrip().endswith(":") and j < idx + 15:
        j += 1
    j += 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return ""
    s = lines[j].strip()
    m = re.match(r'^[rubRUB]*("""|\'\'\'|"|\')', s)
    if not m:
        return ""
    q = m.group(1)
    body = s[m.end():]
    if q in body:
        return body.split(q)[0].strip()
    parts = [body]
    for k in range(j + 1, min(j + 40, len(lines))):
        if q in lines[k]:
            parts.append(lines[k].split(q)[0])
            break
        parts.append(lines[k].strip())
    return " ".join(p.strip() for p in parts if p.strip())


def _full_signature(lines: list[str], idx: int, name: str) -> str:
    sig = lines[idx].strip()
    k = idx
    while sig.count("(") > sig.count(")") and k + 1 < len(lines) and k < idx + 12:
        k += 1
        sig += " " + lines[k].strip()
    sig = re.sub(r"\s+", " ", sig)
    sig = re.sub(r"\s*[{:]\s*$", "", sig) if sig.endswith(("{", ":")) else sig
    return sig[:220]


def extract_symbols(src: SourceFile) -> list[Symbol]:
    lines = src.lines
    is_test = bool(TEST_PATH.search(src.relpath))
    found: list[tuple[int, str, str, str, int]] = []  # (line idx, name, kind, sig, indent)

    if src.lang == "python":
        for i, line in enumerate(lines):
            m = _PY_DEF.match(line) or _PY_CLASS.match(line)
            if m:
                kind = "type" if line.lstrip().startswith("class") else "function"
                found.append((i, m.group("name"), kind, "", len(m.group("ind").expandtabs())))
    else:
        for i, line in enumerate(lines):
            if len(line) > 400 or not line.strip() or line.lstrip().startswith(("//", "*", "/*", "#", "--")):
                continue
            if src.lang == "java":
                m = _JAVA_ABSTRACT.match(line)
                if m and "=" not in line and m.group("name") not in _KEYWORDS:
                    found.append((i, m.group("name"), "method", "", len(line) - len(line.lstrip())))
                    continue
            for kind, rx in _GENERIC:
                m = rx.search(line)
                if not m:
                    continue
                name = m.group("name")
                if name in _KEYWORDS:
                    break
                if rx is _GENERIC[1][1] and "=>" not in line and "function" not in line:
                    continue  # `const x = call(y)` is a call, not a definition
                if kind == "method" and re.match(r"^\s*(?:if|for|while|switch|catch|return|else)\b", line):
                    break
                found.append((i, name, kind, "", len(line) - len(line.lstrip())))
                break

    symbols: list[Symbol] = []
    class_stack: list[tuple[int, str]] = []
    for n, (i, name, kind, _, indent) in enumerate(found):
        if name in _KEYWORDS:
            continue
        while class_stack and class_stack[-1][0] >= indent:
            class_stack.pop()
        parent = class_stack[-1][1] if class_stack else None
        if kind == "type":
            class_stack.append((indent, name))
        if kind == "function" and parent:
            kind = "method"
        end = len(lines)
        for j, *_rest in found[n + 1:]:
            nxt_indent = _rest[3]
            if nxt_indent <= indent:
                end = j
                break
        end = min(end, i + 120)
        doc = _python_docstring(lines, i) if src.lang == "python" else ""
        doc = doc or _leading_comment(lines, i)
        symbols.append(
            Symbol(
                repo=src.repo.name,
                path=src.relpath,
                name=name,
                kind=kind,
                line=i + 1,
                end_line=max(i + 1, end),
                signature=_full_signature(lines, i, name),
                doc=doc[:400],
                is_test=is_test,
                parent=parent,
            )
        )
    return symbols


_CALL_TMPL = r"(?<![\w.$])(?:[\w$]+\.)?{name}\s*\("


def find_call_sites(files: list[SourceFile], sym: Symbol, limit: int = 2) -> list[str]:
    """Real usages of ``sym`` elsewhere: the best evidence of how to call it."""
    rx = re.compile(_CALL_TMPL.format(name=re.escape(sym.name)))
    defn = re.compile(rf"\b(?:def|function|func|fn|fun)\s+{re.escape(sym.name)}\b")
    prod, tests = [], []
    for f in files:
        if f.repo.name != sym.repo or sym.name not in f.text:
            continue
        for ln, line in enumerate(f.lines, 1):
            if f.relpath == sym.path and ln == sym.line:
                continue
            if rx.search(line) and not defn.search(line):
                s = line.strip()
                if s.startswith(("#", "//", "*")) or len(s) > 160:
                    continue
                site = f"{f.relpath}:{ln}  {s}"
                (tests if TEST_PATH.search(f.relpath) else prod).append(site)
                break  # one site per file is enough
        if len(prod) >= limit:
            break
    return (prod + tests)[:limit]


def import_hint(sym: Symbol) -> str:
    p = sym.path
    if p.endswith(".py"):
        mod = p[:-3].replace("/", ".")
        for prefix in ("src.", "lib.", "app."):
            if mod.startswith(prefix):
                mod = mod[len(prefix):]
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        target = sym.parent if sym.kind == "method" and sym.parent else sym.name
        return f"from {mod} import {target}"
    if re.search(r"\.(m?[jt]sx?)$", p):
        target = sym.parent if sym.kind == "method" and sym.parent else sym.name
        module = re.sub(r"(/index)?\.(m?[jt]sx?)$", "", p)
        return f"import {{ {target} }} from '{module}'"
    if p.endswith(".go"):
        return f'import "{p.rsplit("/", 1)[0]}"'
    if p.endswith((".java", ".kt", ".scala")):
        pkg = re.sub(r"^.*?/(java|kotlin|scala)/", "", p).rsplit(".", 1)[0].replace("/", ".")
        return f"import {pkg};"
    return ""
