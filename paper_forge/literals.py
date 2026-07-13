"""Numeric-literal guard: enforce that no number is typed directly into the template.

paper-forge's core promise is that *every number originates from a result unit*. The
compiler checks that ``{{...}}`` placeholders resolve, but nothing stops a hardcoded
number from being typed (or hallucinated by an LLM) directly into the prose. This module
scans a manuscript template for numeric literals that appear **outside** placeholders,
code, YAML front-matter, links, and an allowlist of structural contexts (section-number
headings, citation markers like ``[6]``, ``Table 1`` / ``Figure 2`` labels, and the
References section), so ``paper-forge check`` can fail on any *unexplained* literal.

Escape hatch — mark an intentional literal with an inline HTML comment on the same line::

    The observation hive holds two cameras. <!-- pf-allow-literal: fixed apparatus -->

or add project-wide allow patterns under ``literals.allow`` in ``project.yaml``.

The heuristic only flags numbers that *start* a token (not preceded by a letter), so
result numbers like ``2.67``, ``37%``, ``8D`` and ``1.4`` are caught while identifiers
like ``v17``, ``word2vec``, ``H2O`` and ``F1`` are left alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# A numeric literal that starts a token: optional sign, digits (with optional thousands
# separators / decimals / scientific notation), optional trailing percent. The
# ``(?<![A-Za-z0-9])`` lookbehind skips digits embedded in identifiers (v17, H2O,
# word2vec, F1) — a digit only counts if it is not preceded by a letter or another digit.
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[+-]?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?%?")

# Inline spans masked out before scanning (replaced by spaces to preserve columns).
_INLINE_PROTECTED = (
    re.compile(r"\{\{.*?\}\}"),                       # {{ placeholders }}
    re.compile(r"`[^`]*`"),                           # `inline code`
    re.compile(r"!?\]\([^)]*\)"),                     # ](target) of []() and ![]()
    re.compile(r"<[^>\s]+>"),                          # <autolinks>/<tags>
    re.compile(r"<!--.*?-->"),                        # HTML comments
    re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]"),  # citation markers [6], [1, 2], [3-5]
    re.compile(                                        # Table 1 / Figure 2A / Eq. 3 / Table S1
        r"\b(?:Table|Figure|Fig\.?|Panel|Eq\.?|Equation|Section|Supplementary(?:\s+\w+)?)"
        r"\s+S?\d+[A-Za-z]?\b"
    ),
)

_ALLOW_COMMENT = re.compile(r"<!--\s*pf-allow-literal\b")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_HEADING_NUM = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\b")
_ORDERED_LIST = re.compile(r"^\s*(\d+)[.)]\s")  # markdown ordered-list marker "1. " / "2) "
_REFERENCES = re.compile(r"^#{1,6}\s+(?:\d+\.?\s+)?references\b", re.IGNORECASE)
_FRONTMATTER_FENCE = "---"


@dataclass(frozen=True)
class LiteralFinding:
    """A numeric literal found in manuscript prose (should come from a result unit)."""

    line: int
    column: int
    text: str
    context: str


def _mask(line: str, pattern: re.Pattern[str]) -> str:
    """Replace each match of ``pattern`` with equal-length spaces (preserves columns)."""
    return pattern.sub(lambda m: " " * (m.end() - m.start()), line)


def find_literal_numbers(
    content: str,
    allow: list[str] | None = None,
) -> list[LiteralFinding]:
    """Find numeric literals typed directly into a manuscript template.

    Args:
        content: The manuscript template text.
        allow: Optional list of regex strings; matches are treated as allowed
            (masked out before scanning), for project-specific exceptions.

    Returns:
        A list of :class:`LiteralFinding`, one per offending numeric literal, in
        document order. Empty if the template contains no unexplained literals.
    """
    allow_res = [re.compile(a) for a in (allow or [])]
    findings: list[LiteralFinding] = []

    in_frontmatter = False
    in_code = False
    in_references = False

    for line_num, raw in enumerate(content.splitlines(), start=1):
        stripped = raw.strip()

        # YAML front-matter block at the very top.
        if line_num == 1 and stripped == _FRONTMATTER_FENCE:
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == _FRONTMATTER_FENCE:
                in_frontmatter = False
            continue

        # References section: everything from the heading onward is bibliography.
        if _REFERENCES.match(stripped):
            in_references = True
        if in_references:
            continue

        # Fenced code blocks.
        if _FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code:
            continue

        # Explicit per-line escape hatch.
        if _ALLOW_COMMENT.search(raw):
            continue

        # Mask inline-protected spans and project allow patterns.
        line = raw
        for pattern in _INLINE_PROTECTED:
            line = _mask(line, pattern)
        for pattern in allow_res:
            line = _mask(line, pattern)

        # Mask a leading section number in headings (e.g. "### 3.1 Results").
        heading = _HEADING_NUM.match(line)
        if heading:
            start, end = heading.start(2), heading.end(2)
            line = line[:start] + " " * (end - start) + line[end:]

        # Mask a leading ordered-list marker (e.g. "1. " / "2) ").
        olist = _ORDERED_LIST.match(line)
        if olist:
            start, end = olist.start(1), olist.end(1)
            line = line[:start] + " " * (end - start) + line[end:]

        for match in _NUMBER_RE.finditer(line):
            findings.append(
                LiteralFinding(
                    line=line_num,
                    column=match.start() + 1,
                    text=match.group(0),
                    context=stripped,
                )
            )

    return findings


def check_literals(
    template_path: str | Path,
    allow: list[str] | None = None,
) -> list[LiteralFinding]:
    """Scan a template file for unexplained numeric literals.

    Args:
        template_path: Path to the manuscript template markdown file.
        allow: Optional project-specific allow regexes.

    Returns:
        A list of :class:`LiteralFinding` (empty if the file is clean or missing).
    """
    path = Path(template_path)
    if not path.exists():
        return []
    return find_literal_numbers(path.read_text(encoding="utf-8"), allow=allow)


def format_findings(findings: list[LiteralFinding]) -> str:
    """Render findings as a human-readable, one-per-line report."""
    lines = []
    for f in findings:
        lines.append(f"    line {f.line}:{f.column}  '{f.text}'  in: {f.context}")
    return "\n".join(lines)
