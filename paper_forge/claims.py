"""Verdict-claim guard: enforce that statistical verdicts come from the interpretation layer.

The numeric-literal guard (:mod:`paper_forge.literals`) stops hardcoded *numbers* from
being typed into a template. The more dangerous drift is a hardcoded *verdict*: prose such
as "dancers did not differ significantly from controls" contains no digits, so it survives
the literal guard, a strict compile, and the RQ check — and then silently contradicts the
data the moment a threshold, a dataset, or an analysis changes. The number next to it keeps
updating, because it *is* a placeholder; the claim about it does not.

This is not hypothetical. It is the failure mode paper-forge was extracted to prevent, and
a template can exhibit it while every other check passes.

This module scans a template for verdict language written as flat prose instead of being
resolved through an ``{{interp.*}}`` placeholder, so ``paper-forge check`` can warn and
``paper-forge gate`` can fail on it.

What is *not* flagged:

- text inside ``{{...}}`` placeholders — a verdict resolved by the interpretation engine is
  exactly what this guard wants to see;
- sentences carrying a citation (``(Klein et al. 2010)``, ``[12]``) — a claim about someone
  else's published result is static by nature and does not drift with your data;
- code, YAML front-matter, and the References section;
- anything on a line marked ``<!-- pf-allow-claim: reason -->``.

Escape hatch — mark an intentional static claim with an inline HTML comment on the same
line::

    Sleep deprivation impairs dance precision. <!-- pf-allow-claim: prior literature -->

or add project-wide allow patterns under ``claims.allow`` in ``project.yaml``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Verdict vocabulary. Each entry is (category, pattern). The set is deliberately
# high-precision: a false positive teaches people to switch the guard off, which costs
# more than the claims it would have caught. Extend per project via `claims.extra_patterns`.
_VERDICT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # "significant", "significantly", "non-significant", "significance".
    # Not "significance threshold/level/criterion" — that names the alpha you chose, a
    # Methods statement, not a verdict about a result.
    (
        "significance",
        re.compile(
            r"\b(?:non-?)?signific(?:ant|antly|ance)\b"
            r"(?!\s+(?:threshold|level|criterion|cut-?off))",
            re.IGNORECASE,
        ),
    ),
    # "no difference", "no significant effect", "without any association"
    (
        "null-claim",
        re.compile(
            r"\b(?:no|not|non|without)\s+(?:a\s+|any\s+|the\s+)?"
            r"(?:statistically\s+)?(?:significant\s+)?"
            r"(?:difference|effect|association|correlation|relationship|evidence)\b",
            re.IGNORECASE,
        ),
    ),
    # "does not differ", "did not significantly predict", "do not correlate"
    (
        "negated-verdict",
        re.compile(
            r"\b(?:do|does|did|was|were|is|are)\s+not\s+(?:significantly\s+)?"
            r"(?:differ|predict|correlate|affect|change|exceed|influence)\w*\b",
            re.IGNORECASE,
        ),
    ),
    # "predicts", "predicted", "fails to predict"
    (
        "directional-verdict",
        re.compile(
            r"\b(?:predicts?|predicted|predicting|fail(?:s|ed)?\s+to\s+predict)\b",
            re.IGNORECASE,
        ),
    ),
    # "stronger than", "dominates", "outweighs" — magnitude verdicts between effects
    (
        "magnitude-verdict",
        re.compile(
            r"\b(?:stronger|weaker|larger|smaller)\s+than\b"
            r"|\b(?:dominates?|outweighs?|dominant)\b",
            re.IGNORECASE,
        ),
    ),
)

# Spans masked before scanning (replaced by spaces so columns stay accurate).
_INLINE_PROTECTED: tuple[re.Pattern[str], ...] = (
    re.compile(r"\{\{.*?\}\}"),  # {{ placeholders }} — the correct way to state a verdict
    re.compile(r"`[^`]*`"),  # `inline code`
    re.compile(r"!?\]\([^)]*\)"),  # ](target) of []() and ![]()
    re.compile(r"<!--.*?-->"),  # HTML comments
)

# A sentence containing any of these is a claim about published work, not about your data.
# Deliberately case-SENSITIVE: the leading capital is what distinguishes an author name
# from ordinary prose. Adding re.IGNORECASE would make "sleep and dominates" look like
# "Smith and Jones" and silently exempt real verdicts from the guard.
_CITATION = re.compile(
    r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]"  # [12], [1, 2], [3-5]
    r"|\b[A-Z][A-Za-z'’-]+\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'’-]+)"  # Klein et al. / Smith and Jones
    r"|\(\s*[A-Z][A-Za-z'’-]+[^)]*?(?:19|20)\d\d[a-z]?\s*\)"  # (von Frisch 1967)
    r"|\b[A-Z][A-Za-z'’-]+\s+\(\s*(?:19|20)\d\d[a-z]?\s*\)"  # Frisch (1967)
)

_ALLOW_COMMENT = re.compile(r"<!--\s*pf-allow-claim\b")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_REFERENCES = re.compile(r"^(#{1,6})\s+(?:\d+\.?\s+)?references\b", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6})\s+")
_FRONTMATTER_FENCE = "---"

# Abbreviations whose trailing period must not end a sentence. Masked to an equal-length
# token before splitting so offsets are preserved, then the split is done on the mask.
_ABBREVIATIONS = (
    "et al.",
    "e.g.",
    "i.e.",
    "cf.",
    "vs.",
    "approx.",
    "ca.",
    "Fig.",
    "Figs.",
    "Eq.",
    "Tab.",
    "Ref.",
    "Dr.",
    "Prof.",
)

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ClaimFinding:
    """A statistical verdict asserted in prose rather than resolved from results."""

    line: int
    column: int
    text: str
    category: str
    context: str


def _mask(line: str, pattern: re.Pattern[str]) -> str:
    """Replace each match of ``pattern`` with equal-length spaces (preserves columns)."""
    return pattern.sub(lambda m: " " * (m.end() - m.start()), line)


def _mask_abbreviations(line: str) -> str:
    """Blank out the periods in known abbreviations so they don't end a sentence.

    The result is only used to *locate* sentence boundaries; the original text is what
    gets reported, so replacing '.' with a space here is safe and keeps every offset.
    """
    out = line
    for abbr in _ABBREVIATIONS:
        idx = 0
        while True:
            found = out.lower().find(abbr.lower(), idx)
            if found == -1:
                break
            out = out[:found] + abbr.replace(".", " ") + out[found + len(abbr) :]
            idx = found + len(abbr)
    return out


def _mask_cited_sentences(line: str) -> str:
    """Blank out every sentence that carries a citation.

    A verdict attributed to published work is static by definition, so it must not be
    forced through the interpretation engine. Sentence granularity matters: manuscript
    markdown often puts a whole paragraph on one line, so a line-level rule would let a
    citation anywhere in the paragraph excuse every claim in it.
    """
    boundaries = _mask_abbreviations(line)
    out = list(line)
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(boundaries):
        end = match.start()
        if _CITATION.search(line[start:end]):
            for i in range(start, end):
                out[i] = " "
        start = match.end()
    if _CITATION.search(line[start:]):
        for i in range(start, len(line)):
            out[i] = " "
    return "".join(out)


def find_verdict_claims(
    content: str,
    allow: list[str] | None = None,
    extra_patterns: list[str] | None = None,
) -> list[ClaimFinding]:
    """Find statistical verdicts asserted directly in manuscript prose.

    Args:
        content: The manuscript template text.
        allow: Optional regex strings; matches are masked out before scanning, for
            project-specific exceptions.
        extra_patterns: Optional regex strings adding project-specific verdict
            vocabulary, reported under the category ``"custom"``.

    Returns:
        A list of :class:`ClaimFinding` in document order. Empty if every verdict in the
        template is resolved through a placeholder.
    """
    allow_res = [re.compile(a, re.IGNORECASE) for a in (allow or [])]
    patterns: list[tuple[str, re.Pattern[str]]] = list(_VERDICT_PATTERNS)
    patterns += [("custom", re.compile(p, re.IGNORECASE)) for p in (extra_patterns or [])]

    findings: list[ClaimFinding] = []
    in_frontmatter = False
    in_code = False
    references_level: int | None = None

    for line_num, raw in enumerate(content.splitlines(), start=1):
        stripped = raw.strip()

        if line_num == 1 and stripped == _FRONTMATTER_FENCE:
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == _FRONTMATTER_FENCE:
                in_frontmatter = False
            continue

        # The bibliography is skipped, but only until the next heading at the same or a
        # higher level. Running it to end-of-file would silently skip everything a paper
        # conventionally places after References — Supplementary Information and Figure
        # Legends — which is exactly where unbacked verdicts hide in figure captions.
        heading = _HEADING.match(stripped)
        if references_level is not None:
            if heading and len(heading.group(1)) <= references_level:
                references_level = None
            else:
                continue
        if references_level is None:
            ref = _REFERENCES.match(stripped)
            if ref:
                references_level = len(ref.group(1))
                continue

        if _FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code:
            continue

        if _ALLOW_COMMENT.search(raw):
            continue

        line = raw
        for pattern in _INLINE_PROTECTED:
            line = _mask(line, pattern)
        for pattern in allow_res:
            line = _mask(line, pattern)
        line = _mask_cited_sentences(line)

        # Patterns overlap by design — "no significant difference" matches both the
        # null-claim and significance vocabularies. Report the widest span once rather
        # than the same claim several times, so the count reflects claims, not regexes.
        spans: list[tuple[int, int, str, str]] = []
        for category, pattern in patterns:
            for match in pattern.finditer(line):
                spans.append((match.start(), match.end(), match.group(0), category))

        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept: list[tuple[int, int, str, str]] = []
        for span in spans:
            if any(span[0] >= k[0] and span[1] <= k[1] for k in kept):
                continue
            kept.append(span)

        for start, _end, text, category in kept:
            findings.append(
                ClaimFinding(
                    line=line_num,
                    column=start + 1,
                    text=text,
                    category=category,
                    context=stripped,
                )
            )

    findings.sort(key=lambda f: (f.line, f.column))
    return findings


def check_claims(
    template_path: str | Path,
    allow: list[str] | None = None,
    extra_patterns: list[str] | None = None,
) -> list[ClaimFinding]:
    """Scan a template file for verdicts asserted in prose.

    Args:
        template_path: Path to the manuscript template markdown file.
        allow: Optional project-specific allow regexes.
        extra_patterns: Optional project-specific verdict vocabulary.

    Returns:
        A list of :class:`ClaimFinding` (empty if the file is clean or missing).
    """
    path = Path(template_path)
    if not path.exists():
        return []
    return find_verdict_claims(
        path.read_text(encoding="utf-8"),
        allow=allow,
        extra_patterns=extra_patterns,
    )


def format_findings(findings: list[ClaimFinding]) -> str:
    """Render findings as a human-readable, one-per-line report."""
    lines = []
    for f in findings:
        context = f.context if len(f.context) <= 120 else f.context[:117] + "..."
        lines.append(f"    line {f.line}:{f.column}  [{f.category}] '{f.text}'  in: {context}")
    return "\n".join(lines)
