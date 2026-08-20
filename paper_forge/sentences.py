"""Sentence segmentation for manuscript markdown.

Every guard that reasons about *where* a claim sits needs sentence granularity, and for
the same reason: manuscript markdown routinely puts a whole paragraph on one line, so a
line-level rule lets one citation at the end of a paragraph excuse every claim in it.

The segmentation is deliberately simple — split on sentence-final punctuation followed by
whitespace — with the one refinement that matters in scientific prose: the trailing period
of a known abbreviation ("et al.", "e.g.", "Fig.") must not end a sentence. Abbreviations
are blanked to an equal-length token before splitting, so every offset a caller receives
still indexes into the original line.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# Abbreviations whose trailing period must not end a sentence.
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


def _mask_abbreviations(line: str) -> str:
    """Blank out the periods in known abbreviations so they don't end a sentence.

    The result is only used to *locate* boundaries; callers index into the original text,
    so replacing '.' with a space here is safe and preserves every offset.
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


def sentence_spans(line: str) -> list[tuple[int, int]]:
    """Return the ``(start, end)`` offsets of each sentence in ``line``.

    Offsets index into ``line`` itself. The final span runs to the end of the line, so a
    paragraph without terminal punctuation still yields one sentence.
    """
    boundaries = _mask_abbreviations(line)
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(boundaries):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(line)))
    return spans


def mask_sentences(line: str, is_exempt: Callable[[int, int], bool]) -> str:
    """Blank out every sentence for which ``is_exempt(start, end)`` is true.

    Replacement is space-for-character, so the columns of anything left behind are
    unchanged — a scanner can report positions against the original line.
    """
    out = list(line)
    for start, end in sentence_spans(line):
        if is_exempt(start, end):
            for i in range(start, end):
                out[i] = " "
    return "".join(out)
