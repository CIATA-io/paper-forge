"""Adopting a manuscript that already exists.

``paper-forge init`` assumes an empty directory. The commoner situation is a paper already
half-written — prose in a ``.tex`` or ``.md``, analyses in whatever scripts the author
happens to have, references in a ``.bib`` or in a hand-typed list. Adoption has to work
*around* that material rather than replacing it, because the manuscript is the thing being
adopted, not something the tool provides.

Three constraints follow, and they shape everything here:

- **Nothing is overwritten.** Adoption writes exactly one new file (``project.yaml``) plus a
  baseline snapshot. The manuscript stays where it is and keeps its name; it simply becomes
  the template, and grows slots over time.
- **Nothing is required up front.** A project with no analysis scripts, or no bibliography,
  adopts fine — the guards that have nothing to work on stay quiet until there is something.
- **The numbers must not move.** Wiring a number into a slot should change *where* it comes
  from, never *what it says*. :func:`record_baseline` freezes the manuscript as adopted and
  :func:`compare_numbers` checks a later compile against it, which is the one check that
  proves a migration has not quietly rewritten the paper.

That last point is the method this module exists to automate: it was worked out by hand on a
real migration (port the numbers, diff the compiled output against a frozen reference, only
then convert the verdicts) and lived as a comment in one project's config.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Files that look like manuscripts but are not the paper.
_NOT_A_MANUSCRIPT = re.compile(
    r"^(readme|changelog|license|licence|contributing|todo|notes?|agents?|claude)",
    re.IGNORECASE,
)
# biblatex writes `<job>-blx.bib` next to the real bibliography; it holds control entries,
# not references, and adopting it produces a bibliography with nothing in it.
_GENERATED_BIB = re.compile(r"-blx\.bib$|\.bbl$", re.IGNORECASE)

_LATEX_DOC = re.compile(r"\\documentclass|\\begin\{document\}")
_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".mypy_cache",
}

# A number as it appears in prose: 87, 0.002, 1,312, 31%, -0.42, 1.2e-3.
_NUMBER = re.compile(r"(?<![A-Za-z0-9])[+-]?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?%?")


@dataclass(frozen=True)
class Discovery:
    """What adoption found in a directory that already contains a paper."""

    root: Path
    manuscript: Path | None = None
    kind: str = "markdown"  # markdown | latex
    bibliographies: tuple[Path, ...] = ()
    units_dir: Path | None = None
    results_dir: Path | None = None
    other_candidates: tuple[Path, ...] = ()
    generated_bibs: tuple[Path, ...] = ()

    @property
    def adoptable(self) -> bool:
        return self.manuscript is not None


def _walk(root: Path, suffixes: tuple[str, ...], max_depth: int = 3) -> list[Path]:
    """Files under ``root`` with the given suffixes, skipping build and vendor dirs."""
    out: list[Path] = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in suffixes or not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if len(rel.parts) > max_depth:
            continue
        out.append(path)
    return sorted(out)


def _score_manuscript(path: Path, root: Path) -> tuple[int, int]:
    """Rank a manuscript candidate. Higher sorts first.

    A LaTeX file declaring a document class is almost certainly the paper. Otherwise the
    strongest signal is living in a directory called ``manuscript``/``paper``, and after
    that sheer length — a paper is longer than the notes filed beside it.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (-1, 0)
    score = 0
    if path.suffix.lower() == ".tex" and _LATEX_DOC.search(text):
        score += 100
    if any(p.lower() in {"manuscript", "paper", "ms"} for p in path.relative_to(root).parts[:-1]):
        score += 40
    if path.stem.lower() in {"main", "manuscript", "paper", "article"}:
        score += 20
    return (score, len(text))


def discover(root: str | Path) -> Discovery:
    """Work out what a directory already contains, without changing anything.

    Args:
        root: The project directory holding an existing paper.

    Returns:
        A :class:`Discovery`. ``manuscript`` is ``None`` when nothing looks like a paper,
        which is the one case adoption cannot proceed from.
    """
    root = Path(root)

    candidates = [p for p in _walk(root, (".tex", ".md")) if not _NOT_A_MANUSCRIPT.match(p.stem)]
    ranked = sorted(candidates, key=lambda p: _score_manuscript(p, root), reverse=True)
    manuscript = ranked[0] if ranked else None

    all_bibs = _walk(root, (".bib",))
    generated = tuple(p for p in all_bibs if _GENERATED_BIB.search(p.name))
    bibs = tuple(p for p in all_bibs if p not in generated)

    # Prefer a directory that already looks like result units; fall back to wherever the
    # Python lives. Neither is required.
    units = None
    for guess in ("scripts/result_units", "scripts", "analysis", "src"):
        d = root / guess
        if d.is_dir() and any(d.glob("*.py")):
            units = d
            break

    results = root / "manuscript" / "results"
    if manuscript is not None and manuscript.parent != root:
        results = manuscript.parent / "results"

    return Discovery(
        root=root,
        manuscript=manuscript,
        kind="latex" if manuscript and manuscript.suffix.lower() == ".tex" else "markdown",
        bibliographies=bibs,
        units_dir=units,
        results_dir=results,
        other_candidates=tuple(ranked[1:4]),
        generated_bibs=generated,
    )


def render_config(d: Discovery, project_name: str | None = None) -> str:
    """The ``project.yaml`` for an adopted project.

    Written deliberately quiet: every guard starts as a warning, because a paper being
    adopted is *expected* to fail them at first. Turning them into errors is the milestone
    that marks the migration finished, not the thing that starts it.
    """
    if d.manuscript is None:
        raise ValueError("nothing to adopt: no manuscript found")

    rel = d.manuscript.relative_to(d.root)
    out = rel.with_name(f"{rel.stem}.compiled{rel.suffix}")
    results = d.results_dir.relative_to(d.root) if d.results_dir else Path("manuscript/results")
    name = project_name or d.root.name

    lines = [
        "# paper-forge configuration — adopted from an existing manuscript.",
        "#",
        "# Every guard below starts as a warning on purpose. A paper being adopted is",
        "# expected to fail them at first; `paper-forge check` is the migration worklist,",
        "# and flipping a guard to `enforce: true` is how you mark that part finished.",
        "",
        "project:",
        f'  name: "{name}"',
        "",
        "manuscript:",
        f'  template: "{rel.as_posix()}"',
        f'  output_md: "{out.as_posix()}"',
        f'  results_dir: "{results.as_posix()}"',
        "",
        "result_units:",
    ]
    if d.units_dir is not None:
        lines.append(f'  dir: "{d.units_dir.relative_to(d.root).as_posix()}"')
    lines += [
        "  prefix_map:",
        '    # One line per analysis: "<script stem>": "<short name used in slots>"',
        '    # e.g. "01_dance_precision": "prec"',
        "",
        "literals:",
        "  enforce: false # every number typed in the prose is one still to wire up",
        "  allow: []",
        "claims:",
        "  enforce: false # every verdict in the prose is one still to turn into a rule",
        "  allow: []",
        "unit_verdicts:",
        "  enforce: false",
        "  allow: []",
        "citations:",
    ]
    if d.bibliographies:
        first = d.bibliographies[0].relative_to(d.root).as_posix()
        lines.append(f'  bibliography: "{first}"')
    else:
        lines.append('  # bibliography: "references.bib"   # no .bib found; add one to enable')
    lines += [
        "  enforce: false",
        "  require_verified: false",
        "",
        "rendering:",
        '  engine: "pandoc"',
        "  pandoc_args:",
        '    - "--pdf-engine=xelatex"',
    ]
    if d.bibliographies:
        lines.append('    - "--citeproc"')
    return "\n".join(lines) + "\n"


# --- baseline ---------------------------------------------------------------

BASELINE_DIR = ".paper-forge"
BASELINE_NAME = "baseline"


def baseline_path(root: str | Path, manuscript: Path | None = None) -> Path:
    """Where the adopted-state snapshot of the manuscript lives."""
    suffix = manuscript.suffix if manuscript is not None else ".md"
    return Path(root) / BASELINE_DIR / f"{BASELINE_NAME}{suffix}"


def record_baseline(manuscript: str | Path, root: str | Path) -> Path:
    """Freeze the manuscript as it stands, so a later compile can be checked against it."""
    src = Path(manuscript)
    dest = baseline_path(root, src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def numbers_in(text: str) -> Counter[str]:
    """Every number appearing in a document, counted.

    Compared as a multiset rather than in order: moving a sentence is not a change to the
    paper's claims, but a value appearing or vanishing is.
    """
    return Counter(m.group(0).rstrip(".") for m in _NUMBER.finditer(text))


@dataclass(frozen=True)
class NumberDrift:
    """A number that appears a different number of times than it did at adoption."""

    value: str
    baseline_count: int
    current_count: int

    @property
    def verdict(self) -> str:
        if self.baseline_count == 0:
            return "appeared"
        if self.current_count == 0:
            return "vanished"
        return "count changed"


def compare_numbers(baseline_text: str, current_text: str) -> list[NumberDrift]:
    """Numbers that differ between the adopted baseline and a compiled manuscript.

    An empty result is the thing worth having: it says the slots you wired reproduce the
    paper exactly as it read before, and the migration has not changed any claim.
    """
    before, after = numbers_in(baseline_text), numbers_in(current_text)
    drift = [
        NumberDrift(value=v, baseline_count=before.get(v, 0), current_count=after.get(v, 0))
        for v in sorted(set(before) | set(after))
        if before.get(v, 0) != after.get(v, 0)
    ]
    return drift


def format_drift(drift: list[NumberDrift], limit: int = 20) -> str:
    """Render number drift as a human-readable report."""
    lines = []
    for d in drift[:limit]:
        lines.append(
            f"    {d.value:<14} {d.verdict:<14} baseline {d.baseline_count} → now {d.current_count}"
        )
    if len(drift) > limit:
        lines.append(f"    … and {len(drift) - limit} more")
    return "\n".join(lines)
