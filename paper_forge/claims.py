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
- sentences carrying a citation — a claim about someone else's published result is static
  by nature and does not drift with your data;
- code, YAML front-matter, and the References section;
- anything on a line marked ``<!-- pf-allow-claim: reason -->``.

**What counts as "carrying a citation" depends on whether the project has a bibliography.**
Pass ``bib_keys`` (every key defined in the ``.bib``) and a sentence is exempt only when it
cites a key that actually resolves. Without it — a project using numbered markers and a
hand-written reference list — the guard falls back to recognising citation-*shaped* prose.

That distinction is the whole point. Granting the exemption on prose shape alone inverts
the guard in a ``.bib`` project: a real ``\\citep{klein2010}`` is not prose-shaped and gets
flagged, while a fabricated ``(Klein et al. 2010)`` that appears in no bibliography reads as
a citation and silences the guard. A hallucinated attribution then does two things at once —
invents a reference *and* exempts the verdict attached to it.

Escape hatch — mark an intentional static claim with an inline HTML comment on the same
line::

    Sleep deprivation impairs dance precision. <!-- pf-allow-claim: prior literature -->

or add project-wide allow patterns under ``claims.allow`` in ``project.yaml``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from paper_forge.citations import find_citations
from paper_forge.sentences import mask_sentences

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

# Citation-shaped prose, used ONLY as the fallback exemption for projects with no
# bibliography (see the module docstring). It is deliberately loose — recall matters more
# than precision when the alternative is flagging every literature claim in a numbered-
# reference manuscript. The precision-oriented counterpart, which reports such prose as a
# *problem* in a .bib project, is `citations._PROSE_ATTRIBUTION`.
#
# Deliberately case-SENSITIVE: the leading capital is what distinguishes an author name
# from ordinary prose. Adding re.IGNORECASE would make "sleep and dominates" look like
# "Smith and Jones" and silently exempt real verdicts from the guard.
_CITATION = re.compile(
    r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]"  # [12], [1, 2], [3-5]
    r"|\b[A-Z][A-Za-z'’-]+\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'’-]+)"  # Klein et al. / Smith and J.
    r"|\(\s*[A-Z][A-Za-z'’-]+[^)]*?(?:19|20)\d\d[a-z]?\s*\)"  # (von Frisch 1967)
    r"|\b[A-Z][A-Za-z'’-]+\s+\(\s*(?:19|20)\d\d[a-z]?\s*\)"  # Frisch (1967)
)

_ALLOW_COMMENT = re.compile(r"<!--\s*pf-allow-claim\b")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_REFERENCES = re.compile(r"^(#{1,6})\s+(?:\d+\.?\s+)?references\b", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6})\s+")
_FRONTMATTER_FENCE = "---"


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


def _mask_cited_sentences(line: str, bib_keys: set[str] | None) -> str:
    """Blank out every sentence that carries a citation.

    A verdict attributed to published work is static by definition, so it must not be
    forced through the interpretation engine.

    With ``bib_keys``, "carries a citation" means *cites a key that resolves to a
    bibliography entry* — an unresolvable or fabricated attribution earns no exemption.
    Without it, the guard falls back to citation-shaped prose, which is the right reading
    for a manuscript whose references are numbered markers and a hand-written list.
    """
    if bib_keys is None:
        return mask_sentences(line, lambda s, e: bool(_CITATION.search(line[s:e])))

    resolved = [c.column - 1 for c in find_citations(line) if c.key in bib_keys]
    return mask_sentences(line, lambda s, e: any(s <= col < e for col in resolved))


def find_verdict_claims(
    content: str,
    allow: list[str] | None = None,
    extra_patterns: list[str] | None = None,
    bib_keys: set[str] | None = None,
) -> list[ClaimFinding]:
    """Find statistical verdicts asserted directly in manuscript prose.

    Args:
        content: The manuscript template text.
        allow: Optional regex strings; matches are masked out before scanning, for
            project-specific exceptions.
        extra_patterns: Optional regex strings adding project-specific verdict
            vocabulary, reported under the category ``"custom"``.
        bib_keys: Every identifier that resolves to a bibliography entry — cite keys and
            reference-token digests alike. When given, only a
            sentence citing a key that *resolves* is exempt from the guard; when omitted,
            the guard falls back to recognising citation-shaped prose. See the module
            docstring for why the difference matters.

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
        line = _mask_cited_sentences(line, bib_keys)

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
    bib_keys: set[str] | None = None,
) -> list[ClaimFinding]:
    """Scan a template file for verdicts asserted in prose.

    Args:
        template_path: Path to the manuscript template markdown file.
        allow: Optional project-specific allow regexes.
        extra_patterns: Optional project-specific verdict vocabulary.
        bib_keys: Every key defined in the project bibliography; see
            :func:`find_verdict_claims`.

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
        bib_keys=bib_keys,
    )


def format_findings(findings: list[ClaimFinding]) -> str:
    """Render findings as a human-readable, one-per-line report."""
    lines = []
    for f in findings:
        context = f.context if len(f.context) <= 120 else f.context[:117] + "..."
        lines.append(f"    line {f.line}:{f.column}  [{f.category}] '{f.text}'  in: {context}")
    return "\n".join(lines)
