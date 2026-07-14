"""Smoke tests for the paper-forge CLI: init -> run unit -> check/gate.

These exercise the full happy path end to end, which is exactly what was missing
when several copy-paste-broken examples shipped. A failing `save_results` signature,
a missing entry point, a `render`-vs-`pdf` typo, or a broken gate would all surface here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from paper_forge.cli import main


def _run_scaffolded_unit(project: Path) -> subprocess.CompletedProcess[str]:
    """Execute the scaffolded example result unit and return the completed process."""
    script = project / "scripts" / "result_units" / "01_example.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(project),
    )


def test_init_scaffolds_a_runnable_project(tmp_path: Path) -> None:
    project = tmp_path / "paper"

    assert main(["init", str(project)]) == 0
    assert (project / "project.yaml").exists()
    assert (project / "scripts" / "result_units" / "01_example.py").exists()

    # The generated result unit runs without error and writes its JSON.
    proc = _run_scaffolded_unit(project)
    assert proc.returncode == 0, proc.stderr
    assert (project / "manuscript" / "results" / "01_example.json").exists()

    # check and gate both pass on a freshly scaffolded, compiled project.
    cfg = str(project / "project.yaml")
    assert main(["check", "--config", cfg]) == 0
    assert main(["gate", "--config", cfg]) == 0


def test_gate_fails_on_hardcoded_literal(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # A hardcoded number typed into the prose must fail the gate (literal guard).
    # Inject it into the body, before the (guard-exempt) References section.
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "# References", "We observed 42 events.\n\n# References"
        ),
        encoding="utf-8",
    )
    assert main(["gate", "--config", str(project / "project.yaml")]) != 0


def test_gate_fails_on_unresolved_placeholder(tmp_path: Path) -> None:
    project = tmp_path / "paper"
    assert main(["init", str(project)]) == 0
    assert _run_scaffolded_unit(project).returncode == 0

    # A placeholder no result unit provides must fail the gate (strict compile).
    template = project / "manuscript" / "manuscript_template.md"
    template.write_text(
        template.read_text(encoding="utf-8") + "\nMissing: {{ex.does_not_exist:int}}\n",
        encoding="utf-8",
    )
    assert main(["gate", "--config", str(project / "project.yaml")]) != 0
