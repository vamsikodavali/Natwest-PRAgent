"""Deterministic search engine behind the reuse-check, pr-history and blueprint skills.

The skills (``.claude/skills/*/SKILL.md``) call ``bin/guardian`` to gather ranked,
evidence-backed candidates; Claude then reads the candidates and confirms them.
Standard library only, so it runs in any Python 3.9+ interpreter.
"""

__version__ = "0.1.0"
