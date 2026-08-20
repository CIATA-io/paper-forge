"""Citation guard: enforce that every citation resolves to a real bibliography entry.

The literal guard (:mod:`paper_forge.literals`) stops invented *numbers*; the claim guard
(:mod:`paper_forge.claims`) stops invented *verdicts*. The third thing an LLM invents is a
*reference* — and a citation is the one manuscript element that looks equally plausible
whether or not it exists. ``\\cite{smith2019}`` compiles, reads well, and survives every
other check; only pandoc/BibTeX notices, and only as a warning buried in build output.

This module cross-checks the manuscript against the ``.bib`` file(s) it declares:

- **resolution** — every cited key exists in the bibliography (an unresolvable key is the
  signature of a half-hallucinated citation: the prose was written, the entry never was);
- **coverage** — which bibliography entries are never cited (dead weight, and the signature
  of a bibliography padded with entries no argument in the paper actually needs);
- **uniqueness** — a key defined twice, where BibTeX silently keeps one definition and
  discards the other.

Both LaTeX (``\\cite``, ``\\citep``, ``\\textcite``, ``\\autocite``, …) and pandoc
(``[@key]``, ``[-@key; @other]``, bare ``@key``) citation syntax are recognised, so this
works before and after a project switches its rendering path.

What this guard does **not** do is confirm that a resolvable entry describes a paper that
exists. An entry invented wholesale — plausible title, invented authors and venue — is
internally consistent and passes here. Catching that requires resolving the entry's DOI
against a registry; this module deliberately stays offline and deterministic, and exposes
the parsed entries (:class:`BibEntry`) so a verifier can be layered on top.

Escape hatch — mark a line the scanner should skip::

    Follow @channel for updates. <!-- pf-allow-cite: social handle, not a citation -->

or add project-wide allow patterns under ``citations.allow`` in ``project.yaml``.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from paper_forge.sentences import sentence_spans

# --- BibTeX parsing ---------------------------------------------------------

# Entry types carrying no citation key. @string defines a macro (expanded below);
# @comment and @preamble are pass-through blocks for the LaTeX writer.
_MACRO_TYPE = "string"
_SKIP_TYPES = frozenset({"comment", "preamble"})

_ENTRY_TYPE_RE = re.compile(r"[A-Za-z]+")
_FIELD_NAME_RE = re.compile(r"[A-Za-z0-9_:+.\-]+")

# --- citation extraction ----------------------------------------------------

# Any LaTeX command whose name contains "cite": \cite \citep \citet \citealp \nocite
# (base + natbib) and \parencite \textcite \autocite \footcite \supercite (biblatex).
# Optional star, then up to two optional arguments, then one or more key groups
# (\cites{a}{b} takes several).
_LATEX_CITE = re.compile(
    r"\\(?P<cmd>[A-Za-z]*cite[A-Za-z]*)\*?"
    r"(?:\s*\[[^\]]*\])*"
    r"(?P<groups>(?:\s*\{[^{}]*\})+)",
    re.IGNORECASE,
)

# \citetext{...} takes prose, not keys — its argument must not be read as a citation key.
_NON_KEY_CITE_COMMANDS = frozenset({"citetext"})

_BRACE_GROUP = re.compile(r"\{([^{}]*)\}")

# A pandoc citation key: begins with a letter, digit or underscore, and may contain
# *internal* punctuation. The lookbehind is what keeps an email address (``tim@example.org``)
# and a LaTeX ``\@`` from being read as citations — a bare ``@`` only starts a key when the
# character before it cannot be part of an address.
_PANDOC_CITE = re.compile(
    r"(?<![A-Za-z0-9_.%+\\-])-?@"
    r"(?:\{(?P<braced>[^{}]+)\}|(?P<key>[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/-]*))"
)
_TRAILING_PUNCT = ":.#$%&+?<>~/-"

# --- reference tokens -------------------------------------------------------
#
# A cite key is *guessable*: `smith2019` is exactly the string a language model invents.
# That gives two failure modes, and key resolution only catches one — an invented key that
# happens to collide with a real entry yields a real reference attached to a claim it does
# not support, which no structural check can see.
#
# A reference token is not guessable. `[ref:3f2a9c1d4b6e]` is derived from the bibliography
# entry itself, so a writer can only cite by *copying* a token it was handed. Fabrication
# stops being a heuristic judgement and becomes a lookup: over ~100 references the chance
# of an invented 48-bit token colliding with a real one is ~1e-11.
#
# The scheme is taken from auto_deep_research (`src/citations.py`), with one deliberate
# difference: that resolver *strips* unresolvable tokens, which is right for a generated
# report the reader must never see raw tokens in. A manuscript is authored, not generated,
# so paper-forge fails instead — deleting a fabricated citation would erase the evidence.

TOKEN_LEN = 12
TOKEN_COMMAND = "[ref:]"  # Citation.command for a well-formed token
MALFORMED_TOKEN_COMMAND = "[ref:?]"  # …and for token-shaped text that is not one

# Case-insensitive on purpose: a writer that emits [ref:3F2A…] has made a recoverable
# error — the identifier is real — so it is matched, lowercased, and honoured.
_TOKEN_RE = re.compile(rf"\[ref:([0-9a-fA-F]{{{TOKEN_LEN}}})\]")
# Anything else token-SHAPED: wrong length, not hex, empty. Applied after _TOKEN_RE, so
# whatever this matches is by definition unresolvable. Distinguished from a hallucinated
# token because the cause differs: a hallucinated token is a well-formed identifier for an
# entry that does not exist; a malformed one is a writer failing to copy an identifier.
_MALFORMED_TOKEN_RE = re.compile(r"\[ref:[^\]\s]*\]")

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z ]+")


def ref_digest(identity: str) -> str:
    """The bare hex digest identifying a bibliography entry."""
    return sha256(identity.encode("utf-8")).hexdigest()[:TOKEN_LEN]


def entry_identity(entry: BibEntry) -> str:
    """A canonical string identifying the *work* an entry describes.

    Keyed on the work rather than on the cite key, so a token survives a key rename and is
    identical in two manuscripts that cite the same paper — which also makes two keys for
    one work collide into a single token, surfacing a duplicated reference for free.

    The DOI is used when present because it is the only globally canonical identifier;
    otherwise a normalised first-author surname, year and title stand in.
    """
    if doi := entry.doi:
        return f"doi:{doi.lower()}"
    author = entry.fields.get("author", "")
    first = author.split(" and ")[0].strip()
    surname = first.split(",")[0].strip() if "," in first else first.split(" ")[-1].strip()
    title = _NON_ALNUM.sub("", _WS.sub(" ", entry.fields.get("title", "").lower())).strip()
    return f"bib:{surname.lower()}|{entry.year}|{title}"


def entry_token(entry: BibEntry) -> str:
    """The writable reference token for an entry, e.g. ``[ref:3f2a9c1d4b6e]``."""
    return f"[ref:{ref_digest(entry_identity(entry))}]"


def build_token_map(entries: dict[str, BibEntry]) -> tuple[dict[str, str], list[CitationFinding]]:
    """Map ``digest -> cite key`` for every entry, reporting works that appear twice."""
    token_map: dict[str, str] = {}
    findings: list[CitationFinding] = []
    for key, entry in entries.items():
        digest = ref_digest(entry_identity(entry))
        if (existing := token_map.get(digest)) is not None:
            findings.append(
                CitationFinding(
                    kind="duplicate-work",
                    message=(
                        f"'{key}' and '{existing}' describe the same work "
                        f"({entry_identity(entry)}) — one reference, two entries"
                    ),
                    line=entry.line,
                    source=entry.source,
                )
            )
            continue
        token_map[digest] = key
    return token_map, findings


# An author-year attribution written as prose: "(Klein et al. 2010)", "(von Frisch, 1967)",
# "Smith and Jones (2019)". In a project that has a bibliography, such a string is never a
# citation — citeproc/BibTeX will not render it and it will not appear in the reference
# list — so it is either a fabricated attribution or a citation someone forgot to key.
#
# Precision-oriented on purpose; the recall-oriented counterpart, used only to grant the
# verdict-guard exemption in projects with no bibliography, is `claims._CITATION`. Three
# constraints keep ordinary Methods prose out, each of which was a real false positive:
#
#   1. Name particles are an explicit list, not `[a-z]{2,4}`. A length-bounded lowercase
#      run also matches "of", "in", "the", "with", making "the Declaration of Helsinki
#      (1964)" an attribution.
#   2. A surname must contain a lowercase letter, so acronyms and product names are not
#      author names: WHO, ISO, APA, SPSS, MATLAB.
#   3. The narrative form REQUIRES "et al." or a two-author conjunction. A bare
#      "Name (Year)" is genuinely ambiguous — "Frisch (1967)" and "MATLAB (2021b)" are
#      indistinguishable lexically — so it is not matched at all. The parenthesised form
#      "(von Frisch 1967)" still catches the single-author case, because there the year
#      sits inside the parentheses next to the name; in "Helsinki (1964)" it does not.
#
# The cost is a deliberate miss on narrative single-author prose ("Frisch (1967) showed"),
# taken knowingly: a false positive here teaches people to switch the guard off.
_UPPER = r"[A-ZÀ-ÖØ-ÞĀĂĄĆČĎĐĒĖĘĚĞĢĪĮŁŃŅŇŌŐŔŘŚŞŠŢŤŪŮŰŲŹŻŽ]"
_LOWER = r"[a-zà-öø-ÿß]"
# A surname: initial capital, and a lowercase letter somewhere after it.
_SURNAME = rf"{_UPPER}[\w'’\-]*{_LOWER}[\w'’\-]*"
_PARTICLE = r"(?:von|van|de[nrlsm]?|della|del|di|du|da|dos|das|la|le|ten|ter|el|al|bin|ibn)"
_NAME = rf"(?:{_PARTICLE}\s+){{0,2}}{_SURNAME}"
_ET_AL = r"\s+et\s+al\.?"
_CONJ = rf"\s*(?:,\s*)?(?:and|&)\s+{_NAME}"
# Inside parentheses a lone surname is enough; narratively it is not (constraint 3).
_AUTHORS_PAREN = rf"{_NAME}(?:{_ET_AL}|{_CONJ})?"
_AUTHORS_NARRATIVE = rf"{_NAME}(?:{_ET_AL}|{_CONJ})"
_YEAR = r"(?:19|20)\d\d[a-z]?"
# Sentence punctuation may sit between the year and the closing bracket.
_CLOSE = r"[.;,!?]*\s*\)"
_PROSE_ATTRIBUTION = re.compile(
    rf"\(\s*{_AUTHORS_PAREN}[,;]?\s*{_YEAR}{_CLOSE}"  # (Klein et al. 2010) / (von Frisch, 1967)
    rf"|\b{_AUTHORS_NARRATIVE}\s*\(\s*{_YEAR}{_CLOSE}"  # Klein et al. (2010)
)

_ALLOW_COMMENT = re.compile(r"<!--\s*pf-allow-cite\b")
_FENCE = re.compile(r"^\s*(?:```|~~~)")

# Spans masked before scanning (replaced by spaces so columns stay accurate). Note that
# YAML front-matter is deliberately *not* skipped: a pandoc abstract lives there and cites
# like any other prose.
_INLINE_PROTECTED: tuple[re.Pattern[str], ...] = (
    re.compile(r"\{\{.*?\}\}"),  # {{ placeholders }}
    re.compile(r"`[^`]*`"),  # `inline code`
    re.compile(r"!?\]\([^)]*\)"),  # ](target) of []() and ![]()
    re.compile(r"<!--.*?-->"),  # HTML comments
    re.compile(r"<[^>\s]+>"),  # <autolinks>/<tags>
    re.compile(r"\bhttps?://\S+"),  # bare URLs
)

# Front-matter key naming the bibliography, when project.yaml does not.
_FM_BIBLIOGRAPHY = re.compile(r"^bibliography:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class BibEntry:
    """One bibliography entry, as written in a ``.bib`` file."""

    key: str
    entry_type: str  # article, inproceedings, book, misc, …
    fields: dict[str, str]  # lower-cased field name → brace-stripped value
    source: str = ""  # bib file this entry came from
    line: int = 0

    @property
    def doi(self) -> str:
        """The DOI, normalised to a bare ``10.x/y`` identifier (empty if absent)."""
        raw = self.fields.get("doi", "").strip()
        return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", "", raw, flags=re.IGNORECASE)

    @property
    def year(self) -> str:
        """The publication year (from ``year``, or the leading year of ``date``)."""
        if year := self.fields.get("year", "").strip():
            return year
        match = re.match(r"(\d{4})", self.fields.get("date", "").strip())
        return match.group(1) if match else ""


@dataclass(frozen=True)
class Citation:
    """One citation occurrence in the manuscript."""

    key: str
    line: int
    column: int
    command: str  # "\\citep", "@", …
    context: str


@dataclass(frozen=True)
class CitationFinding:
    """A problem found while cross-checking citations against the bibliography."""

    kind: str  # see _FINDING_ORDER for the full set
    message: str
    line: int = 0
    column: int = 0
    context: str = ""
    source: str = ""  # file the finding refers to (manuscript or .bib)


@dataclass(frozen=True)
class CitationReport:
    """The result of cross-checking a manuscript against its bibliography."""

    entries: dict[str, BibEntry]
    citations: tuple[Citation, ...]
    findings: tuple[CitationFinding, ...]
    bib_files: tuple[Path, ...]
    nocite_all: bool = False
    # digest -> cite key, so a token citation counts toward coverage of its entry.
    token_map: dict[str, str] = field(default_factory=dict)

    @property
    def cited_keys(self) -> set[str]:
        """Every bibliography key the manuscript cites, by key or by token."""
        keys: set[str] = set()
        for citation in self.citations:
            if citation.key == "*" or citation.command == MALFORMED_TOKEN_COMMAND:
                continue
            if citation.command == TOKEN_COMMAND:
                if resolved := self.token_map.get(citation.key):
                    keys.add(resolved)
            else:
                keys.add(citation.key)
        return keys

    @property
    def resolved_keys(self) -> set[str]:
        """Cited keys that exist in the bibliography."""
        return self.cited_keys & set(self.entries)

    @property
    def uncited_keys(self) -> tuple[str, ...]:
        """Bibliography entries the manuscript never cites, in bibliography order."""
        cited = self.cited_keys
        return tuple(k for k in self.entries if k not in cited)

    @property
    def coverage(self) -> float:
        """Fraction of bibliography entries that are cited (1.0 when the bib is empty)."""
        if not self.entries:
            return 1.0
        return len(self.resolved_keys) / len(self.entries)


# --- BibTeX parser ----------------------------------------------------------


def _line_starts(text: str) -> list[int]:
    """Offsets at which each line begins, for offset → line-number lookup."""
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def _line_of(starts: list[int], offset: int) -> int:
    """1-based line number containing ``offset``."""
    return bisect_right(starts, offset)


def _find_matching(text: str, open_at: int, open_ch: str, close_ch: str) -> int:
    """Index of the delimiter closing the one at ``open_at``, or -1 if unbalanced."""
    depth = 0
    for i in range(open_at, len(text)):
        char = text[i]
        if char == open_ch:
            depth += 1
        elif char == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _clean_value(value: str) -> str:
    """Strip BibTeX's capitalisation-protecting braces and collapse whitespace."""
    return re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()


def _read_value(body: str, i: int, macros: dict[str, str]) -> tuple[str, int]:
    """Read one field value starting at ``i``, following ``#`` concatenation.

    Returns the (cleaned) value and the index just past it.
    """
    parts: list[str] = []
    n = len(body)
    while i < n:
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break
        char = body[i]
        if char == "{":
            end = _find_matching(body, i, "{", "}")
            end = n if end == -1 else end
            parts.append(body[i + 1 : end])
            i = end + 1
        elif char == '"':
            # A quoted value may contain braces; a '"' inside braces does not close it.
            depth, j = 0, i + 1
            while j < n:
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                elif body[j] == '"' and depth == 0:
                    break
                j += 1
            parts.append(body[i + 1 : j])
            i = j + 1
        else:
            j = i
            while j < n and body[j] not in ",#" and not body[j].isspace():
                j += 1
            token = body[i:j]
            # A bare token is either a number or a @string macro name.
            parts.append(token if token.isdigit() else macros.get(token.lower(), token))
            i = j
        while i < n and body[i].isspace():
            i += 1
        if i < n and body[i] == "#":  # concatenation — keep reading
            i += 1
            continue
        break
    return _clean_value("".join(parts)), i


def _parse_entry_body(body: str, macros: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Parse the inside of an entry block into ``(citation_key, fields)``."""
    comma = body.find(",")
    if comma == -1:
        return body.strip(), {}
    key = body[:comma].strip()
    fields: dict[str, str] = {}
    i, n = comma + 1, len(body)
    while i < n:
        while i < n and (body[i].isspace() or body[i] == ","):
            i += 1
        name_match = _FIELD_NAME_RE.match(body, i)
        if not name_match:
            break
        i = name_match.end()
        while i < n and body[i].isspace():
            i += 1
        if i >= n or body[i] != "=":
            break
        value, i = _read_value(body, i + 1, macros)
        fields[name_match.group(0).lower()] = value
    return key, fields


def parse_bibtex(text: str, source: str = "") -> list[BibEntry]:
    """Parse BibTeX source into entries, in file order.

    Handles brace- and quote-delimited values, nested braces, ``#`` concatenation and
    ``@string`` macros; skips ``@comment`` and ``@preamble``. Entries appear in the order
    written, and duplicate keys are preserved so the caller can report them.

    Args:
        text: The contents of a ``.bib`` file.
        source: Optional file label recorded on each entry.

    Returns:
        A list of :class:`BibEntry`.
    """
    entries: list[BibEntry] = []
    macros: dict[str, str] = {}
    starts = _line_starts(text)
    i, n = 0, len(text)

    while True:
        at = text.find("@", i)
        if at == -1:
            break
        j = at + 1
        while j < n and text[j].isspace():
            j += 1
        type_match = _ENTRY_TYPE_RE.match(text, j)
        if not type_match:
            i = at + 1
            continue
        entry_type = type_match.group(0).lower()
        j = type_match.end()
        while j < n and text[j].isspace():
            j += 1
        if j >= n or text[j] not in "{(":
            i = at + 1
            continue

        open_ch = text[j]
        close_ch = "}" if open_ch == "{" else ")"
        end = _find_matching(text, j, open_ch, close_ch)
        end = n if end == -1 else end
        body = text[j + 1 : end]
        i = end + 1

        if entry_type in _SKIP_TYPES:
            continue
        if entry_type == _MACRO_TYPE:
            name_match = _FIELD_NAME_RE.match(body.strip())
            if name_match:
                eq = body.find("=")
                if eq != -1:
                    value, _ = _read_value(body, eq + 1, macros)
                    macros[name_match.group(0).lower()] = value
            continue

        key, fields = _parse_entry_body(body, macros)
        if key:
            entries.append(
                BibEntry(
                    key=key,
                    entry_type=entry_type,
                    fields=fields,
                    source=source,
                    line=_line_of(starts, at),
                )
            )
    return entries


def load_bibliography(
    paths: list[Path] | list[str],
) -> tuple[dict[str, BibEntry], list[CitationFinding]]:
    """Load one or more ``.bib`` files into a key → entry map.

    Args:
        paths: Bibliography files, in the order pandoc/BibTeX would read them.

    Returns:
        ``(entries, findings)``. ``findings`` reports unreadable files and duplicate
        keys; on a duplicate, the **first** definition wins, matching BibTeX.
    """
    entries: dict[str, BibEntry] = {}
    findings: list[CitationFinding] = []

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            findings.append(
                CitationFinding(
                    kind="unreadable-bibliography",
                    message=f"bibliography file not found: {path}",
                    source=str(path),
                )
            )
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(
                CitationFinding(
                    kind="unreadable-bibliography",
                    message=f"could not read {path}: {exc}",
                    source=str(path),
                )
            )
            continue

        for entry in parse_bibtex(text, source=str(path)):
            existing = entries.get(entry.key)
            if existing is not None:
                findings.append(
                    CitationFinding(
                        kind="duplicate-key",
                        message=(
                            f"'{entry.key}' is defined twice — "
                            f"{existing.source}:{existing.line} and {entry.source}:{entry.line}. "
                            "BibTeX keeps the first and silently discards the second."
                        ),
                        line=entry.line,
                        source=entry.source,
                    )
                )
                continue
            entries[entry.key] = entry

    return entries, findings


# --- citation extraction ----------------------------------------------------


def _mask(line: str, pattern: re.Pattern[str]) -> str:
    """Replace each match of ``pattern`` with equal-length spaces (preserves columns)."""
    return pattern.sub(lambda m: " " * (m.end() - m.start()), line)


def _scannable_lines(
    content: str,
    allow: list[str] | None = None,
) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line_number, masked_line, stripped_raw)`` for every scannable line.

    Fenced code, lines carrying a ``pf-allow-cite`` comment, and the inline-protected
    spans (placeholders, inline code, link targets, HTML comments, autolinks, URLs) are
    removed. Masking is space-for-character, so columns in the masked line still index
    into the original.
    """
    allow_res = [re.compile(a) for a in (allow or [])]
    in_code = False

    for line_num, raw in enumerate(content.splitlines(), start=1):
        if _FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code or _ALLOW_COMMENT.search(raw):
            continue

        line = raw
        for pattern in _INLINE_PROTECTED:
            line = _mask(line, pattern)
        for pattern in allow_res:
            line = _mask(line, pattern)

        yield line_num, line, raw.strip()


def find_citations(content: str, allow: list[str] | None = None) -> list[Citation]:
    """Find every citation in a manuscript, in document order.

    Recognises LaTeX cite commands (``\\cite``, ``\\citep``, ``\\textcite``, ``\\nocite``,
    …) and pandoc citations (``[@key]``, ``[-@key; @other]``, bare ``@key``). Fenced code,
    inline code, links, URLs, HTML comments and ``{{placeholders}}`` are masked out first.

    Args:
        content: The manuscript text.
        allow: Optional regex strings masked out before scanning, for project-specific
            exceptions (a social handle, a literal ``@`` in prose).

    Returns:
        A list of :class:`Citation`, one per key occurrence.
    """
    citations: list[Citation] = []

    for line_num, line, stripped in _scannable_lines(content, allow):
        found: list[Citation] = []

        latex_matches = list(_LATEX_CITE.finditer(line))
        for match in latex_matches:
            command = match.group("cmd").lower()
            if command in _NON_KEY_CITE_COMMANDS:
                continue
            base = match.start("groups")
            for group in _BRACE_GROUP.finditer(match.group("groups")):
                inner_base = base + group.start(1)
                offset = 0
                for piece in group.group(1).split(","):
                    key = piece.strip()
                    if key:
                        column = inner_base + offset + (len(piece) - len(piece.lstrip())) + 1
                        found.append(
                            Citation(
                                key=key,
                                line=line_num,
                                column=column,
                                command=f"\\{command}",
                                context=stripped,
                            )
                        )
                    offset += len(piece) + 1

        # LaTeX keys are already consumed; blank those spans so a key containing '@'
        # (rare, but legal) is not read a second time as a pandoc citation. Replacements
        # are equal-length, so the columns recorded below stay accurate.
        for match in latex_matches:
            line = line[: match.start()] + " " * (match.end() - match.start()) + line[match.end() :]

        # Reference tokens. Well-formed ones first; whatever the token-shaped pattern
        # matches afterwards is, by construction, not a token anyone can resolve.
        for match in _TOKEN_RE.finditer(line):
            found.append(
                Citation(
                    key=match.group(1).lower(),
                    line=line_num,
                    column=match.start() + 1,
                    command=TOKEN_COMMAND,
                    context=stripped,
                )
            )
        line = _mask(line, _TOKEN_RE)
        for match in _MALFORMED_TOKEN_RE.finditer(line):
            found.append(
                Citation(
                    key=match.group(0),
                    line=line_num,
                    column=match.start() + 1,
                    command=MALFORMED_TOKEN_COMMAND,
                    context=stripped,
                )
            )
        line = _mask(line, _MALFORMED_TOKEN_RE)

        for match in _PANDOC_CITE.finditer(line):
            braced = match.group("braced")
            key = braced.strip() if braced else match.group("key").rstrip(_TRAILING_PUNCT)
            if key:
                found.append(
                    Citation(
                        key=key,
                        line=line_num,
                        column=match.start() + 1,
                        command="@",
                        context=stripped,
                    )
                )

        citations.extend(sorted(found, key=lambda c: c.column))

    return citations


def find_prose_attributions(content: str, allow: list[str] | None = None) -> list[Citation]:
    """Find author-year attributions written as prose instead of as a citation key.

    In a project that has a bibliography, ``(Klein et al. 2010)`` typed into the text is
    never a citation: citeproc and BibTeX both ignore it, so it renders as literal
    parentheses and never reaches the reference list. It is therefore either a fabricated
    attribution or a citation nobody keyed — and in the first case it also used to silence
    the verdict guard for that sentence (see :mod:`paper_forge.claims`).

    Args:
        content: The manuscript text.
        allow: Optional regex strings masked out before scanning.

    Returns:
        A list of :class:`Citation` with ``command="prose"``, whose ``key`` is the matched
        text rather than a bibliography key.
    """
    attributions: list[Citation] = []
    for line_num, line, stripped in _scannable_lines(content, allow):
        for match in _PROSE_ATTRIBUTION.finditer(line):
            attributions.append(
                Citation(
                    key=match.group(0),
                    line=line_num,
                    column=match.start() + 1,
                    command="prose",
                    context=stripped,
                )
            )
    return attributions


# --- cross-check ------------------------------------------------------------


# Fabricated citations first: they are certain, and they are what misleads a reader.
_FINDING_ORDER = {
    "modified-bibliography": -1,
    "hallucinated-token": 0,
    "undefined-key": 1,
    "malformed-token": 2,
    "unkeyed-attribution": 3,
    "unverified-entry": 4,
    "duplicate-work": 5,
    "duplicate-key": 6,
    "unreadable-bibliography": 7,
}


def _trust_findings(
    bib_status: dict[str, str],
    entries: dict[str, BibEntry],
    citations: list[Citation],
    token_map: dict[str, str],
) -> list[CitationFinding]:
    """Report bibliographies that changed after verification, and citations into drafts.

    Reported per *file* rather than per citation: twelve citations into one unverified
    bibliography are one decision for the human to make, not twelve findings to read.
    """
    findings: list[CitationFinding] = []

    for source, state in sorted(bib_status.items()):
        if state == "modified":
            findings.append(
                CitationFinding(
                    kind="modified-bibliography",
                    message=(
                        f"{Path(source).name} changed after it was verified. Re-check the "
                        "entries and re-run `paper-forge verify-bib` to accept the change"
                    ),
                    source=source,
                )
            )

    # Which keys does the manuscript actually cite, by key or by token?
    cited: set[str] = set()
    for citation in citations:
        if citation.command == TOKEN_COMMAND:
            if resolved := token_map.get(citation.key):
                cited.add(resolved)
        elif citation.command != MALFORMED_TOKEN_COMMAND and citation.key != "*":
            cited.add(citation.key)

    unverified: dict[str, list[str]] = {}
    for key in sorted(cited):
        entry = entries.get(key)
        if entry and bib_status.get(entry.source) == "draft":
            unverified.setdefault(entry.source, []).append(key)

    for source, keys in sorted(unverified.items()):
        shown = ", ".join(keys[:5]) + (f" (+{len(keys) - 5} more)" if len(keys) > 5 else "")
        findings.append(
            CitationFinding(
                kind="unverified-entry",
                message=(
                    f"{len(keys)} citation(s) resolve to {Path(source).name}, which no human "
                    f"has verified: {shown}. Check the entries, then run "
                    "`paper-forge verify-bib`"
                ),
                source=source,
            )
        )
    return findings


def _prose_attribution_findings(
    content: str,
    citations: list[Citation],
    entries: dict[str, BibEntry],
    path: Path,
    allow: list[str] | None,
) -> list[CitationFinding]:
    """Report author-year prose in any sentence that carries no resolvable citation.

    Sentence granularity, not line granularity: a paragraph on one line would otherwise let
    a single real citation excuse every fabricated attribution beside it. A sentence that
    *does* cite a resolvable key is left alone — there the prose is phrasing (``\\citet``
    renders exactly that way), not a substitute for a citation.
    """
    resolved_columns: dict[int, list[int]] = {}
    for citation in citations:
        if citation.key in entries:
            resolved_columns.setdefault(citation.line, []).append(citation.column - 1)

    lines = content.splitlines()
    findings: list[CitationFinding] = []
    for attribution in find_prose_attributions(content, allow=allow):
        line_text = lines[attribution.line - 1]
        column = attribution.column - 1
        span = next((s for s in sentence_spans(line_text) if s[0] <= column < s[1]), None)
        if span and any(span[0] <= c < span[1] for c in resolved_columns.get(attribution.line, [])):
            continue
        findings.append(
            CitationFinding(
                kind="unkeyed-attribution",
                message=(
                    f"'{attribution.key}' is an attribution written as prose — it cites "
                    "nothing, will not reach the reference list, and does not exempt the "
                    "sentence from the verdict guard"
                ),
                line=attribution.line,
                column=attribution.column,
                context=attribution.context,
                source=str(path),
            )
        )
    return findings


def check_citations(
    manuscript_path: str | Path,
    bib_paths: list[Path] | list[str],
    allow: list[str] | None = None,
    flag_prose_attributions: bool = True,
    bib_status: dict[str, str] | None = None,
) -> CitationReport:
    """Cross-check a manuscript's citations against its bibliography.

    Args:
        manuscript_path: The manuscript template (or compiled markdown) to scan.
        bib_paths: Bibliography files to resolve citation keys against.
        allow: Optional project-specific allow regexes (see :func:`find_citations`).
        flag_prose_attributions: Report an author-year attribution typed as prose in a
            sentence that cites nothing (see :func:`find_prose_attributions`). Only ever
            applies when the bibliography has entries.
        bib_status: Optional ``{bib_path: state}`` from :mod:`paper_forge.bib_lock`,
            where state is ``verified``, ``draft`` or ``modified``. Supplying it turns on
            the trust checks: citing an entry from an unverified bibliography is reported,
            and a bibliography that changed after being verified is always an error.

    Returns:
        A :class:`CitationReport` carrying the parsed entries, every citation found,
        resolution/uniqueness findings, and the coverage statistic.
    """
    path = Path(manuscript_path)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    entries, findings = load_bibliography(bib_paths)
    token_map, token_findings = build_token_map(entries)
    findings.extend(token_findings)
    citations = find_citations(content, allow=allow)

    nocite_all = False
    for citation in citations:
        if citation.command == MALFORMED_TOKEN_COMMAND:
            findings.append(
                CitationFinding(
                    kind="malformed-token",
                    message=(
                        f"'{citation.key}' is token-shaped but is not a reference token — "
                        f"a token is [ref:] followed by exactly {TOKEN_LEN} hex characters. "
                        "Copy it from `paper-forge tokens` rather than typing it"
                    ),
                    line=citation.line,
                    column=citation.column,
                    context=citation.context,
                    source=str(path),
                )
            )
            continue
        if citation.command == TOKEN_COMMAND:
            if citation.key not in token_map:
                findings.append(
                    CitationFinding(
                        kind="hallucinated-token",
                        message=(
                            f"[ref:{citation.key}] is well-formed but matches no bibliography "
                            "entry. A token can only be copied, never derived, so this "
                            "citation was invented"
                        ),
                        line=citation.line,
                        column=citation.column,
                        context=citation.context,
                        source=str(path),
                    )
                )
            continue
        if citation.key == "*":
            # \nocite{*} pulls in the whole bibliography, so nothing is uncited.
            nocite_all = True
            continue
        if citation.key not in entries:
            findings.append(
                CitationFinding(
                    kind="undefined-key",
                    message=(
                        f"'{citation.key}' cited via {citation.command} "
                        "has no entry in the bibliography"
                    ),
                    line=citation.line,
                    column=citation.column,
                    context=citation.context,
                    source=str(path),
                )
            )

    if flag_prose_attributions and entries:
        findings.extend(_prose_attribution_findings(content, citations, entries, path, allow))

    if bib_status:
        findings.extend(_trust_findings(bib_status, entries, citations, token_map))

    findings.sort(key=lambda f: (_FINDING_ORDER.get(f.kind, 99), f.line, f.column))
    return CitationReport(
        entries=entries,
        citations=tuple(citations),
        findings=tuple(findings),
        bib_files=tuple(Path(p) for p in bib_paths),
        nocite_all=nocite_all,
        token_map=token_map,
    )


def resolve_bibliography(
    config: dict[str, Any],
    base_dir: Path,
    manuscript_path: Path | None = None,
) -> tuple[list[Path], str]:
    """Work out which ``.bib`` files a project uses.

    Looks, in order, at ``citations.bibliography`` in ``project.yaml``, the renderer's
    ``rendering.bibliography`` (what pandoc is already told to use), a ``bibliography:``
    key in the manuscript's YAML front-matter (the pandoc convention), and finally any
    ``.bib`` file sitting next to the project config or the manuscript.

    Args:
        config: The normalised project config (see ``compiler.load_project_config``).
        base_dir: Directory containing ``project.yaml``; relative paths resolve here.
        manuscript_path: The manuscript, whose front-matter is consulted as a fallback.

    Returns:
        ``(paths, origin)`` where ``origin`` names where the setting came from, for
        reporting. ``paths`` is empty when the project has no bibliography.
    """

    def _as_paths(value: Any) -> list[Path]:
        if not value:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        return [(base_dir / str(item)).resolve() for item in items]

    citations_cfg = config.get("citations") or {}
    if paths := _as_paths(citations_cfg.get("bibliography")):
        return paths, "project.yaml (citations.bibliography)"

    render_cfg = config.get("render") or {}
    if paths := _as_paths(render_cfg.get("bibliography")):
        return paths, "project.yaml (rendering.bibliography)"

    if manuscript_path and manuscript_path.exists():
        if paths := _as_paths(_frontmatter_bibliography(manuscript_path)):
            return paths, f"{manuscript_path.name} front-matter"

    discovered: list[Path] = sorted(base_dir.glob("*.bib"))
    if manuscript_path is not None:
        discovered += sorted(p for p in manuscript_path.parent.glob("*.bib"))
    unique = list(dict.fromkeys(p.resolve() for p in discovered))
    if unique:
        return unique, "auto-discovered *.bib"

    return [], "none configured"


def _frontmatter_bibliography(manuscript_path: Path) -> Any:
    """Read ``bibliography:`` from a manuscript's YAML front-matter, if present."""
    text = manuscript_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    try:
        # Front-matter routinely opens a value with '{{', which YAML reads as a flow
        # mapping and rejects; fall back to a line-level match in that case.
        loaded = yaml.safe_load(block)
        if isinstance(loaded, dict):
            return loaded.get("bibliography")
    except yaml.YAMLError:
        pass
    match = _FM_BIBLIOGRAPHY.search(block)
    if not match:
        return None
    value = match.group(1).strip().strip("\"'")
    if value.startswith("[") and value.endswith("]"):
        return [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
    return value or None


def format_findings(findings: list[CitationFinding] | tuple[CitationFinding, ...]) -> str:
    """Render findings as a human-readable, one-per-line report."""
    lines = []
    for finding in findings:
        context = finding.context
        if len(context) > 120:
            context = context[:117] + "..."
        where = f"line {finding.line}:{finding.column}  " if finding.line else ""
        suffix = f"  in: {context}" if context else ""
        lines.append(f"    {where}[{finding.kind}] {finding.message}{suffix}")
    return "\n".join(lines)


def format_coverage(report: CitationReport, limit: int = 20) -> str:
    """Render the coverage statistic and the uncited entries behind it."""
    total = len(report.entries)
    if not total:
        return "  Bibliography is empty."

    used = len(report.resolved_keys)
    lines = [
        f"  Coverage: {used}/{total} bibliography entries cited "
        f"({report.coverage:.0%}); {len(report.citations)} citation(s) in the manuscript."
    ]
    if report.nocite_all:
        lines.append("  \\nocite{*} is present — every entry is rendered regardless of use.")
    uncited = report.uncited_keys
    if uncited:
        shown = ", ".join(uncited[:limit])
        more = f" (+{len(uncited) - limit} more)" if len(uncited) > limit else ""
        lines.append(f"  Never cited ({len(uncited)}): {shown}{more}")
    return "\n".join(lines)
