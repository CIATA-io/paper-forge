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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

METHODS = "methods"  # reserved rq id for descriptive/setup units
VALID_STATUSES = {"open", "answered", "candidate", "dropped"}

# Where a surviving question lands in the paper. This is the axis `status` does not
# capture: `status` is how far along a question is, `role` is where its answer goes.
#   headline    — opens the paper (listed among the questions the introduction poses)
#   reported    — answered in Results, not necessarily headlined up front
#   future_work — the data cannot answer it; appears only in Limitations / Future Work,
#                 never in the introduction. This is the "we asked, we couldn't answer,
#                 so we don't open with it" outcome the lifecycle exists to make explicit.
VALID_ROLES = {"headline", "reported", "future_work"}

_HEADING = re.compile(r"^#{2,3}\s+(\S+)\s+[—-]\s+(.+?)\s*$")
# Accepts "**question:** value" (colon inside the bold) and "**question**: value".
_FIELD = re.compile(
    r"^\s*[-*]\s*\*\*\s*(question|status|units|evidence|role)\s*:?\s*\*\*\s*:?\s*(.*)$",
    re.IGNORECASE,
)

# In an `evidence:` list, a key naming a p-value vs an effect size, by suffix. A question
# can be significant yet negligible — p < alpha with |effect| ~ 0 — so the two are judged
# separately: significance from the p-keys, magnitude from the effect-keys.
_P_KEY = re.compile(r"(?:_p|\.p|_pval|_pvalue)$", re.IGNORECASE)
_EFFECT_KEY = re.compile(r"(?:_r|_rho|_d|_effect|_eta2|_g|\.r)$", re.IGNORECASE)


@dataclass(frozen=True)
class ResearchQuestion:
    id: str
    title: str
    question: str
    status: str
    units: tuple[str, ...]
    # Result keys (prefix.key) whose p-values / effect sizes carry this question's
    # answer. Optional — lets the lifecycle check compare declared prominence against
    # what the data actually shows.
    evidence: tuple[str, ...] = ()
    # Narrative placement; see VALID_ROLES. Empty when not yet assigned.
    role: str = ""


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
            units = tuple(u.strip() for u in cur.get("units", "").split(",") if u.strip())
            evidence = tuple(e.strip() for e in cur.get("evidence", "").split(",") if e.strip())
            out[cur["id"]] = ResearchQuestion(
                id=cur["id"],
                title=cur.get("title", ""),
                question=cur.get("question", ""),
                status=cur.get("status", "open").lower(),
                units=units,
                evidence=evidence,
                role=cur.get("role", "").strip().lower(),
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
            findings.append(
                RqFinding(
                    "bad-status",
                    f"RQ '{rq.id}' has invalid status '{rq.status}' "
                    f"(use: {', '.join(sorted(VALID_STATUSES))})",
                )
            )

    valid_rq_ids = set(registry) | {METHODS}

    # Every unit must declare an rq, and it must resolve.
    for unit in unit_list:
        decl = declared.get(unit, [])
        if not decl:
            findings.append(
                RqFinding(
                    "orphan-unit",
                    f"Unit '{unit}' declares no research question "
                    "(pass rq=... to save_results, or rq='methods')",
                )
            )
            continue
        for rid in decl:
            if rid not in valid_rq_ids:
                findings.append(
                    RqFinding(
                        "unknown-rq",
                        f"Unit '{unit}' declares rq '{rid}', which is not in the registry",
                    )
                )
            elif rid != METHODS and unit not in registry[rid].units:
                findings.append(
                    RqFinding(
                        "registry-mismatch",
                        f"Unit '{unit}' declares rq '{rid}', but RQ '{rid}' "
                        "does not list it under **units:**",
                    )
                )

    # Every non-dropped, non-candidate RQ needs at least one unit; listed units must exist.
    unit_set = set(unit_list)
    for rq in registry.values():
        if rq.status in ("dropped", "candidate"):
            if rq.status == "dropped" and rq.units:
                findings.append(
                    RqFinding(
                        "registry-mismatch",
                        f"RQ '{rq.id}' is dropped but still lists units "
                        f"{list(rq.units)} — remove them",
                    )
                )
            continue
        backing = [u for u in unit_set if rq.id in declared.get(u, [])]
        if not backing and not rq.units:
            findings.append(
                RqFinding("empty-rq", f"RQ '{rq.id}' ({rq.status}) has no result units backing it")
            )
        for u in rq.units:
            if u not in unit_set:
                findings.append(
                    RqFinding(
                        "unknown-unit",
                        f"RQ '{rq.id}' lists unit '{u}', which is not a project unit",
                    )
                )

    return findings


def _rq_evidence_strength(
    rq: ResearchQuestion,
    all_results: dict[str, Any],
    alpha: float,
    min_effect: float,
) -> tuple[str, str] | None:
    """Summarise a question's evidence as (significance, magnitude), or None if unknown.

    Returns a pair drawn from:
        significance ∈ {"significant", "nonsignificant"}
        magnitude    ∈ {"has-effect", "negligible", "unknown"}  ("unknown" = no effect keys)

    None means the question declared no resolvable evidence keys, so strength cannot be
    judged and no evidence-based finding is emitted.
    """
    p_values: list[float] = []
    effects: list[float] = []
    for key in rq.evidence:
        if key not in all_results:
            continue
        val = all_results[key]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        if _P_KEY.search(key):
            p_values.append(float(val))
        elif _EFFECT_KEY.search(key):
            effects.append(abs(float(val)))

    if not p_values and not effects:
        return None

    significance = "significant" if p_values and min(p_values) < alpha else "nonsignificant"
    if effects:
        magnitude = "has-effect" if max(effects) >= min_effect else "negligible"
    else:
        magnitude = "unknown"
    return significance, magnitude


def check_rq_lifecycle(
    registry: dict[str, ResearchQuestion],
    all_results: dict[str, Any],
    template_text: str | None = None,
    alpha: float = 0.05,
    min_effect: float = 0.05,
) -> list[RqFinding]:
    """Check that each question's declared prominence is honest to its evidence and its
    placement in the manuscript.

    This is the layer above the structural RU↔RQ check: it catches the paper opening with
    a question the data cannot answer, and a question buried despite a clear result. It is
    opt-in per question — a question with neither ``role`` nor ``evidence`` is skipped, so
    adopting the lifecycle is incremental.

    The evidence checks are *judgement prompts*, not correctness errors: the tool flags a
    mismatch, the author decides. Only the manuscript-placement contradictions (a retired
    question opening the paper, a dropped question still in the prose) are hard errors,
    because there the registry and the manuscript disagree with each other.

    Args:
        registry: Parsed RQ registry (``parse_registry`` output).
        all_results: Flat ``prefix.key → value`` mapping (as the compiler builds).
        template_text: Manuscript template source. When given, placement is checked using
            ``<!-- rq:<id> -->`` anchors the author drops where each question is discussed.
        alpha: Significance threshold for the evidence check.
        min_effect: |effect| below this counts as negligible. The default (0.05) is a
            "is there anything there at all" floor, deliberately below Cohen's small-effect
            line (0.1) — the check exists to catch effects that are statistically
            significant yet practically zero at large n, not to police effect-size tiers.

    Returns:
        A list of :class:`RqFinding`. Kinds: ``bad-role``, ``evidence-missing``,
        ``headline-weak``, ``buried-signal``, ``intro-has-retired``, ``headline-absent``,
        ``dropped-in-manuscript``.
    """
    findings: list[RqFinding] = []
    intro_ids, body_ids = _manuscript_rq_anchors(template_text) if template_text else (set(), set())

    for rq in registry.values():
        if rq.role and rq.role not in VALID_ROLES:
            findings.append(
                RqFinding(
                    "bad-role",
                    f"RQ '{rq.id}' has invalid role '{rq.role}' (use: {', '.join(sorted(VALID_ROLES))})",
                )
            )

        # An evidence key that resolves to nothing is a typo waiting to mislead.
        for key in rq.evidence:
            if key not in all_results:
                findings.append(
                    RqFinding(
                        "evidence-missing",
                        f"RQ '{rq.id}' cites evidence key '{key}', not found in results",
                    )
                )

        strength = _rq_evidence_strength(rq, all_results, alpha, min_effect)

        # Evidence vs prominence. A headline question should carry a clear result; a
        # negligible or non-significant effect under the spotlight is the exact thing the
        # revisit step is meant to catch. A deliberate null belongs in Results as a
        # reported finding, not as the paper's opening promise.
        if rq.role == "headline" and strength is not None:
            sig, mag = strength
            if sig == "nonsignificant":
                findings.append(
                    RqFinding(
                        "headline-weak",
                        f"RQ '{rq.id}' is role=headline but its evidence is not significant "
                        f"(min p ≥ {alpha}). Open the paper with a question the data answers, "
                        "or set role: future_work.",
                    )
                )
            elif mag == "negligible":
                findings.append(
                    RqFinding(
                        "headline-weak",
                        f"RQ '{rq.id}' is role=headline but its effect is negligible "
                        f"(max |effect| < {min_effect}) despite significance. Confirm it belongs "
                        "up front, or report it as a secondary finding (role: reported).",
                    )
                )

        # The mirror case: a question demoted to future work that the data actually
        # answered. Cheap to surface, easy to forget after a reframing.
        if rq.role == "future_work" and strength == ("significant", "has-effect"):
            findings.append(
                RqFinding(
                    "buried-signal",
                    f"RQ '{rq.id}' is role=future_work but its evidence is significant with a "
                    "non-negligible effect — consider reporting it rather than deferring it.",
                )
            )

        # Manuscript placement. Only meaningful when a template was supplied.
        if template_text is not None:
            anchored = rq.id in intro_ids or rq.id in body_ids
            if rq.status == "dropped" and anchored:
                findings.append(
                    RqFinding(
                        "dropped-in-manuscript",
                        f"RQ '{rq.id}' is dropped but is still anchored in the manuscript — remove it.",
                    )
                )
            elif rq.role == "future_work" and rq.id in intro_ids:
                findings.append(
                    RqFinding(
                        "intro-has-retired",
                        f"RQ '{rq.id}' is role=future_work but appears in the Introduction. A "
                        "question the data cannot answer should not open the paper.",
                    )
                )
            elif rq.role == "headline" and not anchored:
                findings.append(
                    RqFinding(
                        "headline-absent",
                        f"RQ '{rq.id}' is role=headline but has no <!-- rq:{rq.id} --> anchor in "
                        "the manuscript — the promised question is never addressed.",
                    )
                )

    return findings


_RQ_ANCHOR = re.compile(r"<!--\s*rq:\s*(\S+?)\s*-->")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_INTRO_HEADING = re.compile(r"^#{1,6}\s+(?:\d+\.?\s+)?introduction\b", re.IGNORECASE)


def _manuscript_rq_anchors(template_text: str) -> tuple[set[str], set[str]]:
    """Return (rq ids anchored in the Introduction, rq ids anchored elsewhere).

    Placement is declared with ``<!-- rq:<id> -->`` comments. The Introduction runs from
    its heading to the next heading of the same or higher level — the same section model
    the literal and claim guards use.
    """
    intro_ids: set[str] = set()
    body_ids: set[str] = set()
    intro_level: int | None = None

    for line in template_text.splitlines():
        stripped = line.strip()
        heading = _MD_HEADING.match(stripped)
        if heading:
            level = len(heading.group(1))
            if intro_level is not None and level <= intro_level:
                intro_level = None
            if _INTRO_HEADING.match(stripped):
                intro_level = level
        for m in _RQ_ANCHOR.finditer(line):
            (intro_ids if intro_level is not None else body_ids).add(m.group(1))
    return intro_ids, body_ids


def format_rq_findings(findings: list[RqFinding]) -> str:
    return "\n".join(f"    [{f.kind}] {f.message}" for f in findings)
