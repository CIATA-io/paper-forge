"""Research-question registry: enforce that every result unit serves a declared question.

paper-forge's scope discipline is that **the set of research questions bounds the breadth
of the analysis** — every result unit must relate to a research question (RQ), and every RQ
must be backed by at least one unit. This module parses the RQ registry
(`manuscript/research_questions.md` by convention), reads the `rq` field each unit records via
:func:`paper_forge.result_unit.save_results`, and cross-checks the two so `paper-forge
check-rqs` can flag orphan units (analysis with no question) and empty questions.

Growing the analysis is therefore a deliberate act: you add an RQ (status ``candidate`` →
``open``) before its units become legitimate. Narrowing is the same in reverse (status
``dropped``). Descriptive/setup units that characterise the data rather than answer a question
declare ``rq: methods`` and map to the reserved ``methods`` bucket.

Registry format (one block per RQ; parsed leniently)::

    ## RQ-WD — Within-day topological memory
    - **question:** Does the proximity network carry within-day memory of waggle activity?
    - **status:** answered
    - **units:** 01_within_day_mc, 02_feeder_analysis, 06_signal_weather
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

METHODS = "methods"  # reserved rq id for descriptive/setup units
VALID_STATUSES = {"open", "answered", "candidate", "dropped"}

_HEADING = re.compile(r"^#{2,3}\s+(\S+)\s+[—-]\s+(.+?)\s*$")
# Accepts "**question:** value" (colon inside the bold) and "**question**: value".
_FIELD = re.compile(
    r"^\s*[-*]\s*\*\*\s*(question|status|units)\s*:?\s*\*\*\s*:?\s*(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResearchQuestion:
    id: str
    title: str
    question: str
    status: str
    units: tuple[str, ...]


@dataclass(frozen=True)
class RqFinding:
    kind: str  # orphan-unit | unknown-rq | empty-rq | registry-mismatch | unknown-unit | bad-status
    message: str


def parse_registry(path: str | Path) -> dict[str, ResearchQuestion]:
    """Parse an RQ registry markdown file into ``{id: ResearchQuestion}``."""
    path = Path(path)
    if not path.exists():
        return {}
    out: dict[str, ResearchQuestion] = {}
    cur: dict[str, Any] | None = None

    def _flush() -> None:
        if cur and cur.get("id"):
            units = tuple(
                u.strip() for u in cur.get("units", "").split(",") if u.strip()
            )
            out[cur["id"]] = ResearchQuestion(
                id=cur["id"], title=cur.get("title", ""),
                question=cur.get("question", ""),
                status=cur.get("status", "open").lower(), units=units,
            )

    for line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADING.match(line)
        if m:
            _flush()
            cur = {"id": m.group(1), "title": m.group(2)}
            continue
        if cur is not None:
            fm = _FIELD.match(line)
            if fm:
                cur[fm.group(1).lower()] = fm.group(2).strip()
    _flush()
    return out


def _declared_rqs(results_dir: Path) -> dict[str, list[str]]:
    """Map unit stem → list of rq ids it declares (from each result JSON envelope)."""
    import json

    declared: dict[str, list[str]] = {}
    if not results_dir.is_dir():
        return declared
    for jp in sorted(results_dir.glob("*.json")):
        try:
            env = json.loads(jp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rq = env.get("rq")
        if isinstance(rq, str):
            rq = [rq]
        declared[jp.stem] = list(rq) if isinstance(rq, list) else []
    return declared


def check_research_questions(
    registry_path: str | Path,
    results_dir: str | Path,
    units: list[str] | None = None,
) -> list[RqFinding]:
    """Cross-check the RQ registry against the units and their declared ``rq`` fields.

    Args:
        registry_path: Path to the RQ registry markdown file.
        results_dir: Directory of result JSONs (each may carry an ``rq`` field).
        units: The project's unit stems (e.g. from ``project.yaml`` prefix_map). If
            omitted, the stems found in ``results_dir`` are used.

    Returns:
        A list of :class:`RqFinding` (empty if the RU↔RQ mapping is consistent).
    """
    registry = parse_registry(registry_path)
    declared = _declared_rqs(Path(results_dir))
    unit_list = list(units) if units is not None else sorted(declared.keys())
    findings: list[RqFinding] = []

    # Status sanity.
    for rq in registry.values():
        if rq.status not in VALID_STATUSES:
            findings.append(RqFinding("bad-status",
                f"RQ '{rq.id}' has invalid status '{rq.status}' (use: {', '.join(sorted(VALID_STATUSES))})"))

    valid_rq_ids = set(registry) | {METHODS}

    # Every unit must declare an rq, and it must resolve.
    for unit in unit_list:
        decl = declared.get(unit, [])
        if not decl:
            findings.append(RqFinding("orphan-unit",
                f"Unit '{unit}' declares no research question (pass rq=... to save_results, or rq='methods')"))
            continue
        for rid in decl:
            if rid not in valid_rq_ids:
                findings.append(RqFinding("unknown-rq",
                    f"Unit '{unit}' declares rq '{rid}', which is not in the registry"))
            elif rid != METHODS and unit not in registry[rid].units:
                findings.append(RqFinding("registry-mismatch",
                    f"Unit '{unit}' declares rq '{rid}', but RQ '{rid}' does not list it under **units:**"))

    # Every non-dropped, non-candidate RQ needs at least one unit; listed units must exist.
    unit_set = set(unit_list)
    for rq in registry.values():
        if rq.status in ("dropped", "candidate"):
            if rq.status == "dropped" and rq.units:
                findings.append(RqFinding("registry-mismatch",
                    f"RQ '{rq.id}' is dropped but still lists units {list(rq.units)} — remove them"))
            continue
        backing = [u for u in unit_set if rq.id in declared.get(u, [])]
        if not backing and not rq.units:
            findings.append(RqFinding("empty-rq",
                f"RQ '{rq.id}' ({rq.status}) has no result units backing it"))
        for u in rq.units:
            if u not in unit_set:
                findings.append(RqFinding("unknown-unit",
                    f"RQ '{rq.id}' lists unit '{u}', which is not a project unit"))

    return findings


def format_rq_findings(findings: list[RqFinding]) -> str:
    return "\n".join(f"    [{f.kind}] {f.message}" for f in findings)
