"""Frozen-verdict guard: stop a result unit from emitting a verdict it did not derive.

The verdict-claim guard (:mod:`paper_forge.claims`) scans the manuscript template, and the
compiler masks every ``{{...}}`` span before it looks. So a verdict routed *through* a result
unit is invisible to it::

    # 01_example.py
    results["main_interp"] = "The treatment significantly reduced the outcome."

    # manuscript_template.md
    {{ex.main_interp}}

Every guard passes and "significantly reduced" reaches the PDF. Nothing scans result units,
so this is the one place a frozen verdict has never been checked — and it is exactly the
shape an agent produces after reading ``p = .003`` once.

What separates a sound interpretation string from a frozen one is not *where* it lives but
whether it was **derived**. This is sound, because the branch is re-evaluated on every run::

    if p < 0.05:
        interp = "The effect was significant."
    else:
        interp = "No significant effect was observed."

and this is a verdict frozen at whatever was true the day it was typed::

    interp = "The effect was significant."

The two are indistinguishable in the result JSON — both are just a string — which is why
this guard reads the *source*. A verdict-bearing string literal is flagged unless it sits
inside a conditional construct (``if``/``else``, a ternary, ``match``), because only then is
the wording a function of the data.

Escape hatch — a Python comment on the same line::

    label = "not significant"  # pf-allow-verdict: axis label, not a claim

or add project-wide allow patterns under ``unit_verdicts.allow`` in ``project.yaml``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from paper_forge.claims import _VERDICT_PATTERNS

_ALLOW_COMMENT = re.compile(r"#\s*pf-allow-verdict\b")

# Calls whose string arguments address a human reading a terminal, not the manuscript.
_IO_FUNCTIONS = frozenset({"print", "warn", "warning", "info", "debug", "error", "critical", "log"})


@dataclass(frozen=True)
class UnitVerdictFinding:
    """A verdict string a result unit states outright instead of deriving."""

    file: str
    line: int
    column: int
    text: str
    category: str
    context: str


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of Constant nodes that are docstrings, which are prose *about* the code."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                out.add(id(first.value))
    return out


def _match_verdict(text: str) -> tuple[str, str] | None:
    """The widest verdict phrase in ``text``, as ``(category, matched_text)``.

    The vocabularies overlap by design — "no significant difference" matches both the
    null-claim and significance patterns — so the widest match is reported rather than
    whichever pattern happens to come first in the list. Same reasoning as
    :mod:`paper_forge.claims`: the report should name the claim, not the regex.
    """
    best: tuple[str, str] | None = None
    for category, pattern in _VERDICT_PATTERNS:
        if found := pattern.search(text):
            if best is None or len(found.group(0)) > len(best[1]):
                best = (category, found.group(0))
    return best


class _Scanner(ast.NodeVisitor):
    """Collect verdict strings that are not derived from a conditional."""

    def __init__(self, filename: str, lines: list[str], docstrings: set[int]) -> None:
        self.filename = filename
        self.lines = lines
        self.docstrings = docstrings
        self.findings: list[UnitVerdictFinding] = []
        self._derived = 0  # inside if / ternary / match — the wording tracks the data
        self._suppressed = 0  # inside print()/logging/raise/assert — not manuscript prose

    # --- contexts that make a string derived ---
    def _visit_conditional(self, node: ast.AST) -> None:
        self._derived += 1
        self.generic_visit(node)
        self._derived -= 1

    visit_If = _visit_conditional
    visit_IfExp = _visit_conditional
    visit_Match = _visit_conditional

    # --- contexts that take the string out of scope ---
    def _visit_suppressed(self, node: ast.AST) -> None:
        self._suppressed += 1
        self.generic_visit(node)
        self._suppressed -= 1

    visit_Raise = _visit_suppressed
    visit_Assert = _visit_suppressed

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name in _IO_FUNCTIONS:
            self._visit_suppressed(node)
        else:
            self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self._derived or self._suppressed:
            return
        if not isinstance(node.value, str) or id(node) in self.docstrings:
            return
        verdict = _match_verdict(node.value)
        if verdict is None:
            return
        line_text = self.lines[node.lineno - 1] if node.lineno <= len(self.lines) else ""
        if _ALLOW_COMMENT.search(line_text):
            return
        category, text = verdict
        self.findings.append(
            UnitVerdictFinding(
                file=self.filename,
                line=node.lineno,
                column=node.col_offset + 1,
                text=text,
                category=category,
                context=line_text.strip(),
            )
        )


def find_frozen_verdicts(
    source: str,
    filename: str = "",
    allow: list[str] | None = None,
) -> list[UnitVerdictFinding]:
    """Find verdict strings a result unit states rather than derives.

    Args:
        source: Python source of one result unit.
        filename: Label recorded on each finding.
        allow: Optional regex strings; a string literal matching one is ignored.

    Returns:
        Findings in source order. Empty when every verdict in the unit is derived.
    """
    try:
        tree = ast.parse(source, filename=filename or "<unit>")
    except SyntaxError:
        # A unit that does not parse is the test suite's problem, not this guard's.
        return []

    scanner = _Scanner(filename, source.splitlines(), _docstring_nodes(tree))
    scanner.visit(tree)

    allow_res = [re.compile(a, re.IGNORECASE) for a in (allow or [])]
    return [f for f in scanner.findings if not any(r.search(f.context) for r in allow_res)]


def check_unit_verdicts(
    units_dir: str | Path,
    allow: list[str] | None = None,
) -> list[UnitVerdictFinding]:
    """Scan every result unit in ``units_dir`` for frozen verdicts.

    Args:
        units_dir: Directory of result-unit scripts (``scripts/result_units`` by convention).
        allow: Optional project-specific allow regexes.

    Returns:
        Findings across all units, in filename order. Empty if the directory is absent —
        a project may keep its units elsewhere, and this guard is not the place to complain.
    """
    directory = Path(units_dir)
    if not directory.is_dir():
        return []
    findings: list[UnitVerdictFinding] = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        findings.extend(find_frozen_verdicts(source, filename=str(path), allow=allow))
    return findings


def format_findings(findings: list[UnitVerdictFinding]) -> str:
    """Render findings as a human-readable, one-per-line report."""
    lines = []
    for f in findings:
        context = f.context if len(f.context) <= 100 else f.context[:97] + "..."
        name = Path(f.file).name if f.file else "<unit>"
        lines.append(f"    {name}:{f.line}:{f.column}  [{f.category}] '{f.text}'  in: {context}")
    return "\n".join(lines)
