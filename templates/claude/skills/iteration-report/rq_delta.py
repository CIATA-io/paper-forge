#!/usr/bin/env python3
"""rq_delta — deterministic evidence diff for the iteration-report skill.

Computes how each research question's evidence keys moved between the last commit
(baseline) and the current working tree, and classifies each move as halt / decision /
notification. The iteration-report skill runs this instead of asking the agent to do
arithmetic over `git diff` text — the halt decision is too consequential to leave to
prose parsing.

Run from the project root:

    python .claude/skills/iteration-report/rq_delta.py            # human-readable
    python .claude/skills/iteration-report/rq_delta.py --json     # machine-readable

Reads project.yaml (prefix_map, results_dir, research_questions), the RQ registry, the
current result JSONs, and their versions at git HEAD. Requires paper_forge importable.

Exit codes: 0 = no halt-class change; 2 = at least one halt-class change; 1 = error
(baseline unavailable, dirty preconditions) — treated by the skill as a DECISION, never
silently as "no change".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    from paper_forge.compiler import load_project_config
    from paper_forge.research_questions import evidence_delta, parse_registry
except Exception as e:  # pragma: no cover - environment guard
    print(f"rq_delta: cannot import paper_forge ({e})", file=sys.stderr)
    sys.exit(1)


def _git_show(ref_path: str) -> str | None:
    """Return file contents at a git ref (e.g. 'HEAD:manuscript/results/x.json'), or None."""
    try:
        out = subprocess.run(
            ["git", "show", ref_path], capture_output=True, text=True, timeout=15
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    return out.stdout if out.returncode == 0 else None


def _flatten(results_dir: Path, prefix_map: dict, *, from_head: bool) -> dict:
    """Build a flat prefix.key -> value map from the current tree or from HEAD."""
    flat: dict = {}
    stem_to_prefix = dict(prefix_map)
    for jp in sorted(results_dir.glob("*.json")):
        stem = jp.stem
        prefix = stem_to_prefix.get(stem, stem)
        if from_head:
            rel = jp.as_posix()
            # results_dir may be absolute; git needs a repo-relative path.
            try:
                rel = jp.relative_to(_repo_root()).as_posix()
            except ValueError:
                rel = jp.as_posix()
            raw = _git_show(f"HEAD:{rel}")
            if raw is None:
                continue  # file is new this iteration; no baseline for its keys
            env = json.loads(raw)
        else:
            env = json.loads(jp.read_text(encoding="utf-8"))
        for k, v in (env.get("results", env) or {}).items():
            flat[f"{prefix}.{k}"] = v
    return flat


def _repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10
    )
    return Path(out.stdout.strip()) if out.returncode == 0 else Path.cwd()


def _baseline_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def main() -> int:
    as_json = "--json" in sys.argv
    config_path = Path("project.yaml")
    if not config_path.exists():
        print("rq_delta: project.yaml not found (run from the project root)", file=sys.stderr)
        return 1

    config = load_project_config(config_path)
    base = config_path.parent
    results_dir = base / config["results_dir"]
    registry_path = base / config.get("research_questions", "manuscript/research_questions.md")
    prefix_map = config.get("prefix_map") or {}

    registry = parse_registry(registry_path)
    if not registry:
        print("rq_delta: no research questions found", file=sys.stderr)
        return 1

    new_results = _flatten(results_dir, prefix_map, from_head=False)
    old_results = _flatten(results_dir, prefix_map, from_head=True)
    if not old_results:
        print(
            "rq_delta: no baseline at HEAD for any result key — cannot certify halt "
            "conditions 2/3. Treat as a DECISION and commit a baseline.",
            file=sys.stderr,
        )
        return 1

    deltas = evidence_delta(registry, old_results, new_results)
    halts = [d for d in deltas if d.classification == "halt"]

    if as_json:
        print(
            json.dumps(
                {
                    "baseline": _baseline_sha(),
                    "deltas": [d.__dict__ for d in deltas],
                    "halt_count": len(halts),
                },
                indent=2,
            )
        )
        return 2 if halts else 0

    print(f"[rq_delta] baseline = HEAD ({_baseline_sha()}); {len(deltas)} evidence key(s) moved")
    if not deltas:
        print("  no evidence-key changes this iteration.")
        return 0
    order = {"halt": 0, "decision": 1, "notification": 2}
    for d in sorted(deltas, key=lambda x: (order[x.classification], x.rq_id, x.key)):
        old = "—" if d.old is None else f"{d.old:.4g}"
        new = "—" if d.new is None else f"{d.new:.4g}"
        print(f"  {d.classification.upper():12} {d.rq_id} [{d.role}] {d.key}: {old} → {new}")
        print(f"               {d.reason}")
    return 2 if halts else 0


if __name__ == "__main__":
    sys.exit(main())
