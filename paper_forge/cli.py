"""Command-line interface for paper-forge.

Provides the ``paper-forge`` CLI with subcommands:
    - ``init``       — scaffold a new project
    - ``adopt``      — set up paper-forge around a manuscript that already exists
    - ``baseline``   — check an adopted paper still says what it said
    - ``compile``    — compile manuscript (resolve placeholders)
    - ``check``      — validate placeholders + literal, claim and citation guards
    - ``check-refs`` — cross-check citations against the bibliography, report coverage
    - ``tokens``     — print the reference token for each bibliography entry
    - ``verify-bib`` — record bibliography files as human-verified
    - ``check-rqs``  — verify every result unit serves a declared research question
    - ``gate``       — strict compile + literal, verdict and citation guards + check-rqs
    - ``pdf``        — render compiled markdown to PDF
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path


def _cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a new paper-forge project."""
    project_dir = Path(args.dir)
    project_name = project_dir.name or "my-paper"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (project_dir / "manuscript" / "results").mkdir(parents=True, exist_ok=True)
    (project_dir / "manuscript" / "figures").mkdir(parents=True, exist_ok=True)
    (project_dir / "scripts" / "result_units").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests").mkdir(exist_ok=True)

    # Create project.yaml (nested format)
    config_path = project_dir / "project.yaml"
    if not config_path.exists():
        config_path.write_text(
            f"""\
# paper-forge project configuration

project:
  name: "{project_name}"
  title: "My Paper Title"

manuscript:
  template: "manuscript/manuscript_template.md"
  output_md: "manuscript/manuscript.md"
  output_pdf: "manuscript/manuscript.pdf"
  results_dir: "manuscript/results"
  figures_dir: "manuscript/figures"

result_units:
  prefix_map:
    "01_example": "ex"

# Statistical verdicts are resolved from results at compile time as {{interp.<key>}}.
interpretations: interpretations.yaml

# For verdicts the built-in functions cannot express, point at a module defining
# register(engine) and use its functions in interpretations.yaml.
# interpretation_functions: scripts/interp_functions.py

# Guards. `paper-forge gate` enforces all of them regardless of these settings.
literals:
  enforce: false # no hardcoded numbers in the template
  allow: []
claims:
  enforce: false # no hardcoded verdicts in the template
  allow: []
  extra_patterns: []
unit_verdicts:
  enforce: false # no verdict stated outright in a result unit
  allow: []
citations:
  # bibliography: "references.bib"   # else: rendering.bibliography, front-matter, *.bib
  enforce: false # every cite key must resolve to a bibliography entry
  min_coverage: 0 # >0 also fails when too few entries are cited
  flag_prose_attributions: true # an attribution must be a citation, not prose
  expand_tokens: auto # auto | pandoc | latex | off
  require_verified: false # true = citing an unverified .bib fails the gate
  allow: []

execution:
  python: "uv run python"

rendering:
  engine: "pandoc"
  pandoc_args:
    - "--pdf-engine=xelatex"
    - "--number-sections"
""",
            encoding="utf-8",
        )
        print(f"  Created {config_path}")

    # Create interpretations.yaml — where statistical verdicts come from
    interp_path = project_dir / "interpretations.yaml"
    if not interp_path.exists():
        interp_path.write_text(
            """\
# Interpretation rules — the only place a statistical VERDICT may be decided.
#
# The template supplies numbers via {{prefix.key:formatter}}. It must never supply the
# claim *about* those numbers ("significant", "does not differ", "stronger than"): prose
# written by hand freezes the verdict that held the day it was typed, and the number
# beside it keeps updating while the sentence does not.
#
# Each rule turns raw statistics into a phrase at compile time, used as {{interp.<key>}}.
#
# Built-ins: correlation_effect, correlation_qualifier, comparison, significance_stars.
# Register your own with InterpretationEngine.register_function().
# A parameter suffixed `_key` is looked up in the results; anything else is a literal.

rules:
  # {{interp.main_effect}} → "significantly reduces" / "does not significantly change"
  main_effect:
    function: correlation_effect
    output_key: main_effect
    args:
      p_key: ex.p_value
      rho_key: ex.effect
      pos_verb: increases
      neg_verb: reduces

  # {{interp.main_qualifier}} → "This moderate negative effect" / "This non-significant result"
  main_qualifier:
    function: correlation_qualifier
    output_key: main_qualifier
    args:
      p_key: ex.p_value
      rho_key: ex.effect
""",
            encoding="utf-8",
        )
        print(f"  Created {interp_path}")

    # Create manuscript template
    manuscript_path = project_dir / "manuscript" / "manuscript_template.md"
    if not manuscript_path.exists():
        manuscript_path.write_text(
            """\
---
title: "My Paper Title"
author: "Author Name"
date: "2026"
abstract: |
  We analyzed {{ex.n_samples:int}} samples and found an effect size
  of {{ex.effect:r}} (p = {{ex.p_value:p}}).
---

# Introduction

Background and motivation.

# Methods

We collected {{ex.n_samples:int}} samples and analyzed them using...

# Results

The treatment {{interp.main_effect}} the outcome
(r = {{ex.effect:r}}, p = {{ex.p_value:p}}, {{ex.p_value:stars}}).

# Discussion

{{interp.main_qualifier}} is consistent with...

# References
""",
            encoding="utf-8",
        )
        print(f"  Created {manuscript_path}")

    # Create .gitkeep files
    for keep in ["manuscript/results/.gitkeep", "manuscript/figures/.gitkeep"]:
        keep_path = project_dir / keep
        if not keep_path.exists():
            keep_path.touch()

    # Create result unit __init__.py
    init_path = project_dir / "scripts" / "result_units" / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""Result units for this project."""\n',
            encoding="utf-8",
        )

    # Create example result unit
    example_path = project_dir / "scripts" / "result_units" / "01_example.py"
    if not example_path.exists():
        example_path.write_text(
            '''\
#!/usr/bin/env python3
"""01_example — Example result unit.

Output: manuscript/results/01_example.json
Prefix: ex
"""
from pathlib import Path
from paper_forge.result_unit import save_results

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "manuscript" / "results"


def main() -> None:
    # Your analysis here...
    # Emit numbers only. Verdicts ("significantly reduced") belong in
    # interpretations.yaml, so they are re-decided from the data on every run
    # instead of frozen into a string here.
    results = {
        "n_samples": 150,
        "p_value": 0.003,
        "effect": -0.42,
    }

    save_results("01_example", results, output_dir=RESULTS_DIR)


if __name__ == "__main__":
    main()
''',
            encoding="utf-8",
        )
        print(f"  Created {example_path}")

    # Create Makefile
    makefile_path = project_dir / "Makefile"
    if not makefile_path.exists():
        makefile_path.write_text(
            """\
.PHONY: all units compile check check-refs tokens verify-bib pdf pipeline clean help

PYTHON ?= uv run python

UNIT_SCRIPTS := $(sort $(wildcard scripts/result_units/[0-9]*.py))

all: compile

units:
\t@echo "Running result units..."
\t@for script in $(UNIT_SCRIPTS); do echo "  $$script"; $(PYTHON) $$script; done

compile:
\t@echo "Compiling manuscript..."
\t@uv run paper-forge compile

check:
\t@echo "Checking placeholders, literals, verdicts and citations..."
\t@uv run paper-forge check

check-refs:
\t@echo "Cross-checking citations against the bibliography..."
\t@uv run paper-forge check-refs

tokens:
\t@echo "Reference tokens for this project's bibliography:"
\t@uv run paper-forge tokens

verify-bib:
\t@echo "Recording the bibliography as human-verified..."
\t@uv run paper-forge verify-bib

pdf:
\t@echo "Rendering PDF..."
\t@uv run paper-forge pdf

pipeline: units compile pdf
\t@echo "Pipeline complete."

clean:
\trm -f manuscript/manuscript.md manuscript/manuscript.pdf
\trm -f manuscript/results/*.json

help:
\t@echo "Targets: all units compile check check-refs tokens verify-bib pdf pipeline clean"
""",
            encoding="utf-8",
        )
        print(f"  Created {makefile_path}")

    # Create .gitignore
    gitignore_path = project_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(
            """\
manuscript/manuscript.md
*.pdf
__pycache__/
.venv/
.ruff_cache/
""",
            encoding="utf-8",
        )
        print(f"  Created {gitignore_path}")

    print(f"\n  Project scaffolded at {project_dir}/")
    print("  Next steps:")
    print("    1. Edit scripts/result_units/01_example.py with your analysis")
    print("    2. Run: make units")
    print("    3. Edit manuscript/manuscript_template.md with your text")
    print("    4. Run: make pipeline")
    return 0


def _cmd_adopt(args: argparse.Namespace) -> int:
    """Adopt an existing manuscript: write a config around it and report the work ahead."""
    from paper_forge.adopt import discover, record_baseline, render_config

    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 1

    config_path = root / "project.yaml"
    if config_path.exists() and not args.dry_run:
        print(
            f"ERROR: {config_path} already exists — this project is already on paper-forge.\n"
            "  To pick up newer paper-forge features, upgrade the package and run "
            "`paper-forge check`;\n  new guards report as warnings and nothing needs "
            "reconfiguring.",
            file=sys.stderr,
        )
        return 1

    discovery = discover(root)
    if args.manuscript:
        chosen = Path(args.manuscript)
        chosen = chosen if chosen.is_absolute() else root / chosen
        if not chosen.exists():
            print(f"ERROR: manuscript not found: {chosen}", file=sys.stderr)
            return 1
        discovery = replace(
            discovery,
            manuscript=chosen,
            kind="latex" if chosen.suffix.lower() == ".tex" else "markdown",
        )

    if not discovery.adoptable:
        print(
            "ERROR: no manuscript found here. Point at one explicitly:\n"
            "  paper-forge adopt . --manuscript path/to/paper.tex",
            file=sys.stderr,
        )
        return 1

    rel = discovery.manuscript.relative_to(root)
    print(f"  Manuscript:   {rel} ({discovery.kind})")
    if discovery.other_candidates:
        names = ", ".join(p.name for p in discovery.other_candidates)
        print(f"                (also considered {names} — use --manuscript to override)")
    print(f"  Bibliography: {', '.join(p.name for p in discovery.bibliographies) or 'none found'}")
    if discovery.generated_bibs:
        skipped = ", ".join(p.name for p in discovery.generated_bibs)
        print(f"                (ignored {skipped} — generated by biblatex, not references)")
    units = discovery.units_dir
    print(f"  Analyses:     {units.relative_to(root) if units else 'none found'}")

    config = render_config(discovery, project_name=args.name)
    if args.dry_run:
        print("\n  --dry-run: project.yaml would be:\n")
        print("\n".join(f"    {line}" for line in config.splitlines()))
        return 0

    config_path.write_text(config, encoding="utf-8")
    print(f"\n  Wrote {config_path.relative_to(root)}")
    baseline = record_baseline(discovery.manuscript, root)
    print(f"  Froze the manuscript as adopted at {baseline.relative_to(root)}")
    print("  Nothing else was changed.")

    _print_worklist(root, config_path)
    return 0


def _print_worklist(root: Path, config_path: Path) -> None:
    """Report what stands between an adopted paper and a passing gate."""
    from paper_forge.claims import check_claims
    from paper_forge.compiler import load_project_config
    from paper_forge.literals import check_literals
    from paper_forge.unit_verdicts import check_unit_verdicts

    try:
        config = load_project_config(config_path)
    except Exception as exc:  # a freshly written config that cannot load is a bug worth seeing
        print(f"\n  (could not read back the config to size the work: {exc})", file=sys.stderr)
        return

    template = root / config["manuscript"]
    literals = len(check_literals(template))
    claims = len(check_claims(template))
    verdicts = len(check_unit_verdicts(root / config.get("units_dir", "scripts/result_units")))

    print("\n  The work ahead — `paper-forge check` is this list, with line numbers:")
    print(f"    {literals:>4}  numbers typed in the prose, to wire to an analysis")
    print(f"    {claims:>4}  verdicts in the prose, to turn into interpretation rules")
    print(f"    {verdicts:>4}  verdicts stated outright in an analysis script")
    print("\n  Nothing fails yet: every guard starts as a warning. Work the list down, then")
    print("  set `enforce: true` per guard as each one reaches zero.")
    print("\n  Check you have not changed the paper while wiring it up:")
    print("    paper-forge baseline")


def _cmd_baseline(args: argparse.Namespace) -> int:
    """Compare the compiled manuscript against the snapshot taken when it was adopted."""
    from paper_forge.adopt import baseline_path, compare_numbers, format_drift, record_baseline
    from paper_forge.compiler import load_project_config

    try:
        config = load_project_config(args.config)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    root = Path(args.config).parent.resolve()
    template = root / config["manuscript"]
    compiled = root / config["output"]

    if args.record:
        dest = record_baseline(compiled if compiled.exists() else template, root)
        print(f"  Baseline recorded from {dest.name}. Later compiles are compared against it.")
        return 0

    base = baseline_path(root, template)
    if not base.exists():
        print(
            f"ERROR: no baseline at {base.relative_to(root)}.\n"
            "  Record one with `paper-forge baseline --record` (do this before you start "
            "wiring slots).",
            file=sys.stderr,
        )
        return 1
    if not compiled.exists():
        print(
            f"ERROR: nothing compiled at {compiled.relative_to(root)} — run "
            "`paper-forge compile` first.",
            file=sys.stderr,
        )
        return 1

    drift = compare_numbers(base.read_text(encoding="utf-8"), compiled.read_text(encoding="utf-8"))
    if not drift:
        print("  Every number in the compiled manuscript matches the baseline.")
        print("  Wiring the slots has not changed what the paper says.")
        return 0

    print(
        f"\n  {len(drift)} number(s) differ from the manuscript as adopted. Each is either a "
        "slot\n  wired to the wrong value, or a real change you meant to make:",
        file=sys.stderr,
    )
    print(format_drift(drift), file=sys.stderr)
    print(
        "\n  If they are all intended, re-record with `paper-forge baseline --record`.",
        file=sys.stderr,
    )
    return 1 if args.strict else 0


def _cmd_compile(args: argparse.Namespace) -> int:
    """Compile the manuscript."""
    from paper_forge.compiler import compile_manuscript

    try:
        compile_manuscript(config_path=args.config, check_only=False, strict=args.strict)
        return 0
    except SystemExit:
        # Raised by --strict when placeholders are unresolved.
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _check_literals(config_path: str, strict_literals: bool) -> int:
    """Run the numeric-literal guard on the template. Returns an exit code delta."""
    from paper_forge.compiler import load_project_config
    from paper_forge.literals import check_literals, format_findings

    config = load_project_config(config_path)
    template_path = Path(config_path).parent / config["manuscript"]
    lit_cfg = config.get("literals", {}) or {}
    findings = check_literals(template_path, allow=lit_cfg.get("allow", []))

    if not findings:
        print("  No hardcoded numeric literals in the template.")
        return 0

    enforce = strict_literals or bool(lit_cfg.get("enforce", False))
    label = "ERROR" if enforce else "WARNING"
    print(
        f"\n  {label}: {len(findings)} hardcoded numeric literal(s) in the template — "
        "numbers should come from result units (or mark with "
        "'<!-- pf-allow-literal: reason -->'):",
        file=sys.stderr,
    )
    print(format_findings(findings), file=sys.stderr)
    return 1 if enforce else 0


def _bibliography_keys(config: dict, base_dir: Path, template_path: Path) -> set[str] | None:
    """Every identifier that resolves to a bibliography entry, or None if there is none.

    That means cite keys *and* reference-token digests: a sentence cited as
    ``[ref:3f2a9c1d4b6e]`` is exactly as resolved as one cited as ``\\citep{key}``, and
    must earn the same exemption.

    The verdict guard needs this to decide what "carries a citation" means. With a
    bibliography, only a citation that *resolves* exempts a sentence; without one, the
    guard falls back to citation-shaped prose (see :mod:`paper_forge.claims`).
    """
    from paper_forge.citations import build_token_map, load_bibliography, resolve_bibliography

    bib_paths, _ = resolve_bibliography(config, base_dir, template_path)
    if not bib_paths:
        return None
    entries, _ = load_bibliography(bib_paths)
    if not entries:
        # The bibliography is configured but yielded nothing — a mistyped path, an
        # unreadable file, or an empty .bib. Returning an empty *set* would mean "a
        # bibliography exists and nothing in the manuscript resolves", which flags every
        # literature claim in the paper. The citation guard already reports the real
        # cause once; fall back instead, so one root problem produces one error rather
        # than an avalanche of unrelated ones.
        return None
    token_map, _ = build_token_map(entries)
    return set(entries) | set(token_map)


def _check_claims(config_path: str, strict_claims: bool) -> int:
    """Run the verdict-claim guard on the template. Returns an exit code delta."""
    from paper_forge.claims import check_claims, format_findings
    from paper_forge.compiler import load_project_config

    config = load_project_config(config_path)
    base_dir = Path(config_path).parent
    template_path = base_dir / config["manuscript"]
    claim_cfg = config.get("claims", {}) or {}
    findings = check_claims(
        template_path,
        allow=claim_cfg.get("allow", []),
        extra_patterns=claim_cfg.get("extra_patterns", []),
        bib_keys=_bibliography_keys(config, base_dir, template_path),
    )

    if not findings:
        print("  No unbacked statistical verdicts in the template.")
        return 0

    enforce = strict_claims or bool(claim_cfg.get("enforce", False))
    label = "ERROR" if enforce else "WARNING"
    print(
        f"\n  {label}: {len(findings)} statistical verdict(s) asserted in template prose — "
        "a verdict must come from an {{interp.*}} placeholder so it tracks the data "
        "(or mark it with '<!-- pf-allow-claim: reason -->'):",
        file=sys.stderr,
    )
    print(format_findings(findings), file=sys.stderr)
    return 1 if enforce else 0


def _check_unit_verdicts(config_path: str, strict_units: bool) -> int:
    """Run the frozen-verdict guard over the result units. Returns an exit-code delta.

    The verdict-claim guard scans the template, and the compiler masks every ``{{...}}``
    span before it looks — so a verdict routed through a result unit has never been checked
    by anything. This is the guard for that path.
    """
    from paper_forge.compiler import load_project_config
    from paper_forge.unit_verdicts import check_unit_verdicts, format_findings

    config = load_project_config(config_path)
    base_dir = Path(config_path).parent
    unit_cfg = config.get("unit_verdicts", {}) or {}
    units_dir = base_dir / config.get("units_dir", "scripts/result_units")
    findings = check_unit_verdicts(units_dir, allow=unit_cfg.get("allow", []))

    if not findings:
        print("  No frozen verdicts in the result units.")
        return 0

    enforce = strict_units or bool(unit_cfg.get("enforce", False))
    label = "ERROR" if enforce else "WARNING"
    print(
        f"\n  {label}: {len(findings)} verdict(s) stated outright in a result unit — a verdict "
        "must be derived from the statistic (branch on it, or use interpretations.yaml), or it "
        "freezes at whatever was true when it was typed "
        "(or mark the line with '# pf-allow-verdict: reason'):",
        file=sys.stderr,
    )
    print(format_findings(findings), file=sys.stderr)
    return 1 if enforce else 0


def _check_refs(config_path: str, strict_refs: bool, bib_override: list[str] | None = None) -> int:
    """Run the citation guard against the project bibliography. Returns an exit-code delta.

    Resolution failures (a cited key with no entry) and duplicate keys are the errors.
    Coverage is reported as a statistic and only fails the check when the project sets
    ``citations.min_coverage`` — an uncited entry is untidy, not wrong.
    """
    from paper_forge.bib_lock import format_status, status_for
    from paper_forge.citations import (
        check_citations,
        format_coverage,
        format_findings,
        resolve_bibliography,
    )
    from paper_forge.compiler import load_project_config

    config = load_project_config(config_path)
    base_dir = Path(config_path).parent
    template_path = base_dir / config["manuscript"]
    cite_cfg = config.get("citations", {}) or {}

    if bib_override:
        bib_paths = [Path(p) for p in bib_override]
        origin = "--bib"
    else:
        bib_paths, origin = resolve_bibliography(config, base_dir, template_path)

    if not bib_paths:
        print("  No bibliography configured — citation guard skipped.")
        return 0

    print(f"  Bibliography ({origin}): {', '.join(str(p) for p in bib_paths)}")
    statuses = status_for(bib_paths, base_dir)
    print(format_status(statuses))
    report = check_citations(
        template_path,
        bib_paths,
        allow=cite_cfg.get("allow", []),
        flag_prose_attributions=bool(cite_cfg.get("flag_prose_attributions", True)),
        bib_status={str(s.path): s.state for s in statuses},
    )
    print(format_coverage(report))

    exit_code = 0
    enforce = strict_refs or bool(cite_cfg.get("enforce", False))
    require_verified = bool(cite_cfg.get("require_verified", False))

    # The three severities are governed separately, because they answer different
    # questions and `gate` must not conflate them:
    #   modified-bibliography — always fatal. A file a human signed off has changed.
    #   unverified-entry      — fatal only under `require_verified`. Otherwise a draft
    #                           bibliography is a normal working state, and failing on it
    #                           would break every existing project that has a .bib and no
    #                           lock file the moment this shipped.
    #   everything else       — the fabrication findings, governed by `enforce`/`--strict`.
    modified = [f for f in report.findings if f.kind == "modified-bibliography"]
    unverified = [f for f in report.findings if f.kind == "unverified-entry"]
    fabrication = [f for f in report.findings if f.kind not in _TRUST_KINDS]

    fatal = bool(modified) or (bool(unverified) and require_verified) or (fabrication and enforce)
    if fatal:
        exit_code |= 1

    if report.findings:
        label = "ERROR" if fatal else "WARNING"
        undefined = sum(1 for f in report.findings if f.kind == "undefined-key")
        unkeyed = sum(1 for f in report.findings if f.kind == "unkeyed-attribution")
        detail = ", ".join(
            part
            for part in (
                f"{undefined} unresolvable key(s)" if undefined else "",
                f"{unkeyed} unkeyed attribution(s)" if unkeyed else "",
            )
            if part
        )
        print(
            f"\n  {label}: {len(report.findings)} citation problem(s)"
            + (f" — {detail}" if detail else "")
            + ". A cited key must exist in the bibliography, and an attribution must be a "
            "citation rather than prose (or mark the line with "
            "'<!-- pf-allow-cite: reason -->'):",
            file=sys.stderr,
        )
        print(format_findings(report.findings), file=sys.stderr)
        # Severity was decided above by `fatal`; findings are printed either way.
    else:
        print("  Every citation resolves to a bibliography entry.")

    min_coverage = float(cite_cfg.get("min_coverage", 0) or 0)
    if min_coverage and report.coverage < min_coverage:
        print(
            f"\n  ERROR: bibliography coverage {report.coverage:.0%} is below the "
            f"required {min_coverage:.0%} ({len(report.uncited_keys)} entries never cited).",
            file=sys.stderr,
        )
        exit_code |= 1

    return exit_code


def _cmd_check(args: argparse.Namespace) -> int:
    """Check placeholders (and, unless disabled, literals, verdicts and citations)."""
    from paper_forge.compiler import compile_manuscript

    exit_code = 0
    try:
        compile_manuscript(config_path=args.config, check_only=True)
        print("  All placeholders resolved successfully.")
    except SystemExit:
        exit_code = 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not args.no_literals:
        try:
            exit_code |= _check_literals(args.config, args.strict_literals)
        except Exception as e:
            print(f"ERROR (literal check): {e}", file=sys.stderr)
            return 1

    if not getattr(args, "no_claims", False):
        try:
            exit_code |= _check_claims(args.config, getattr(args, "strict_claims", False))
        except Exception as e:
            print(f"ERROR (claim check): {e}", file=sys.stderr)
            return 1

    if not getattr(args, "no_refs", False):
        try:
            exit_code |= _check_refs(args.config, getattr(args, "strict_refs", False))
        except Exception as e:
            print(f"ERROR (citation check): {e}", file=sys.stderr)
            return 1

    if not getattr(args, "no_units", False):
        try:
            exit_code |= _check_unit_verdicts(args.config, getattr(args, "strict_units", False))
        except Exception as e:
            print(f"ERROR (unit verdict check): {e}", file=sys.stderr)
            return 1

    return exit_code


def _cmd_verify_bib(args: argparse.Namespace) -> int:
    """Record bibliography files as human-verified.

    Promoting a bibliography from draft to verified is the moment a human takes
    responsibility for its entries, so it is deliberately an explicit act that leaves a
    reviewable diff in ``bibliography.lock`` rather than something a build step infers.
    """
    from paper_forge.bib_lock import format_status, load_bibliography_counts, verify_files
    from paper_forge.citations import resolve_bibliography
    from paper_forge.compiler import load_project_config

    try:
        config = load_project_config(args.config)
        base_dir = Path(args.config).parent
        template_path = base_dir / config["manuscript"]

        if args.files:
            bib_paths = [Path(f) for f in args.files]
        else:
            bib_paths, origin = resolve_bibliography(config, base_dir, template_path)
            if not bib_paths:
                print(
                    "ERROR: no bibliography configured — set 'citations.bibliography' in "
                    "project.yaml or name the files to verify.",
                    file=sys.stderr,
                )
                return 1
            print(f"  Bibliography ({origin})")

        missing = [p for p in bib_paths if not p.exists()]
        if missing:
            for path in missing:
                print(f"ERROR: bibliography not found: {path}", file=sys.stderr)
            return 1

        statuses = verify_files(
            bib_paths,
            base_dir,
            entry_counts=load_bibliography_counts(bib_paths),
            note=args.note or "",
        )
        print(format_status(statuses))
        print(f"\n  Recorded in {base_dir / 'bibliography.lock'} — commit it.")
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cmd_tokens(args: argparse.Namespace) -> int:
    """Print the reference token for every bibliography entry.

    This table is the artifact you hand a writer. A token is derived from the entry, so it
    can be copied but never guessed — which is what makes an unresolvable token in the
    manuscript certain evidence of a fabricated citation rather than a heuristic guess.
    """
    import json

    from paper_forge.citations import (
        build_token_map,
        entry_token,
        load_bibliography,
        resolve_bibliography,
    )
    from paper_forge.compiler import load_project_config

    try:
        config = load_project_config(args.config)
        base_dir = Path(args.config).parent
        template_path = base_dir / config["manuscript"]

        if args.bib:
            bib_paths = [Path(b) for b in args.bib]
        else:
            bib_paths, origin = resolve_bibliography(config, base_dir, template_path)
            if not bib_paths:
                print(
                    "ERROR: no bibliography configured — set 'citations.bibliography' in "
                    "project.yaml or pass --bib.",
                    file=sys.stderr,
                )
                return 1
            print(f"  Bibliography ({origin})", file=sys.stderr)

        entries, findings = load_bibliography(bib_paths)
        _, dup_findings = build_token_map(entries)

        if args.format == "json":
            print(
                json.dumps(
                    {
                        key: {
                            "token": entry_token(entry),
                            "type": entry.entry_type,
                            "year": entry.year,
                            "doi": entry.doi,
                            "title": entry.fields.get("title", ""),
                            "author": entry.fields.get("author", ""),
                        }
                        for key, entry in entries.items()
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            for key, entry in entries.items():
                title = entry.fields.get("title", "")
                if len(title) > 58:
                    title = title[:55] + "..."
                print(f"{entry_token(entry)}  {key:<24}  {entry.year:<6}  {title}")

        for finding in findings + dup_findings:
            print(f"  WARNING [{finding.kind}] {finding.message}", file=sys.stderr)
        print(f"\n  {len(entries)} entries.", file=sys.stderr)
        return 0
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cmd_check_refs(args: argparse.Namespace) -> int:
    """Cross-check every citation against the bibliography and report coverage."""
    try:
        return _check_refs(args.config, args.strict, bib_override=args.bib)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


# Citation findings whose severity is governed by the bibliography trust tier rather than
# by the `enforce`/--strict switch that governs fabrication findings.
_TRUST_KINDS = frozenset({"modified-bibliography", "unverified-entry"})

# Lifecycle findings where the registry contradicts the manuscript or itself: hard.
# The evidence-vs-prominence prompts (headline-weak, buried-signal) and coverage gaps
# (headline-absent) are advisory — a mismatch the author resolves, not a build breaker.
_RQ_LIFECYCLE_ERRORS = {
    "bad-role",
    "evidence-missing",
    "intro-has-retired",
    "dropped-in-manuscript",
}


def _cmd_check_rqs(args: argparse.Namespace) -> int:
    """Check the RU↔RQ mapping and, when questions opt into it, the RQ lifecycle."""
    from paper_forge.compiler import load_all_results, load_project_config
    from paper_forge.research_questions import (
        check_research_questions,
        check_rq_lifecycle,
        format_rq_findings,
        parse_registry,
    )

    try:
        config = load_project_config(args.config)
        base_dir = Path(args.config).parent
        registry = base_dir / config.get("research_questions", "manuscript/research_questions.md")
        results_dir = base_dir / config["results_dir"]
        prefix_map = config.get("prefix_map") or {}
        units = list(prefix_map.keys()) or None

        if not registry.exists():
            print(
                f"ERROR: research-question registry not found: {registry}\n"
                "  Create it (see paper_forge.research_questions), or set "
                "'research_questions:' in project.yaml.",
                file=sys.stderr,
            )
            return 1

        exit_code = 0

        # 1. Structural RU↔RQ mapping (always an error when broken).
        structural = check_research_questions(registry, results_dir, units)
        if structural:
            print(f"\n  {len(structural)} research-question mapping issue(s):", file=sys.stderr)
            print(format_rq_findings(structural), file=sys.stderr)
            exit_code = 1
        else:
            print("  Every result unit maps to a research question, and every question is backed.")

        # 2. Lifecycle — evidence-linked prominence + manuscript placement. Opt-in: only
        # runs when at least one question declares a role or evidence keys.
        parsed = parse_registry(registry)
        if any(rq.role or rq.evidence for rq in parsed.values()):
            all_results = load_all_results(results_dir, prefix_map)
            template_path = base_dir / config["manuscript"]
            template_text = (
                template_path.read_text(encoding="utf-8") if template_path.exists() else None
            )
            life = check_rq_lifecycle(parsed, all_results, template_text=template_text)
            errors = [f for f in life if f.kind in _RQ_LIFECYCLE_ERRORS]
            warnings = [f for f in life if f.kind not in _RQ_LIFECYCLE_ERRORS]
            if errors:
                print(f"\n  ERROR: {len(errors)} RQ lifecycle contradiction(s):", file=sys.stderr)
                print(format_rq_findings(errors), file=sys.stderr)
                exit_code = 1
            if warnings:
                print(
                    f"\n  WARNING: {len(warnings)} RQ prominence issue(s) to confirm:",
                    file=sys.stderr,
                )
                print(format_rq_findings(warnings), file=sys.stderr)
            if not life:
                print("  RQ lifecycle: prominence matches evidence and manuscript placement.")

        return exit_code
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def _cmd_gate(args: argparse.Namespace) -> int:
    """Run the full consistency gate: strict compile + every guard + the RQ check.

    Chains the checks that must all pass before a manuscript is trustworthy, and
    returns non-zero if any fails. This is the deterministic gate the Claude-native
    review loop runs before scoring. The research-question check runs only when a
    registry is present, so ``gate`` is usable with or without the RQ layer.
    """
    from paper_forge.compiler import compile_manuscript, load_project_config

    rc = 0
    print("  [gate] strict compile + placeholder check ...")
    try:
        compile_manuscript(config_path=args.config, check_only=False, strict=True)
    except SystemExit:
        rc = 1
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("  [gate] numeric-literal guard ...")
    try:
        rc |= _check_literals(args.config, strict_literals=True)
    except Exception as e:
        print(f"ERROR (literal check): {e}", file=sys.stderr)
        rc = 1

    print("  [gate] verdict-claim guard ...")
    try:
        rc |= _check_claims(args.config, strict_claims=True)
    except Exception as e:
        print(f"ERROR (claim check): {e}", file=sys.stderr)
        rc = 1

    print("  [gate] frozen-verdict guard ...")
    try:
        rc |= _check_unit_verdicts(args.config, strict_units=True)
    except Exception as e:
        print(f"ERROR (unit verdict check): {e}", file=sys.stderr)
        rc = 1

    # Citation guard — a no-op (and never a failure) when the project has no bibliography.
    print("  [gate] citation guard ...")
    try:
        rc |= _check_refs(args.config, strict_refs=True)
    except Exception as e:
        print(f"ERROR (citation check): {e}", file=sys.stderr)
        rc = 1

    # Research-question check — only when a registry is present.
    try:
        config = load_project_config(args.config)
        registry = Path(args.config).parent / config.get(
            "research_questions", "manuscript/research_questions.md"
        )
        if registry.exists():
            print("  [gate] research-question check ...")
            rc |= _cmd_check_rqs(args)
        else:
            print("  [gate] research-question check skipped (no registry).")
    except Exception as e:
        print(f"ERROR (rq check): {e}", file=sys.stderr)
        rc = 1

    print(f"\n  [gate] {'PASS' if rc == 0 else 'FAIL'}", file=sys.stderr if rc else sys.stdout)
    return rc


def _cmd_pdf(args: argparse.Namespace) -> int:
    """Render the compiled manuscript to PDF."""
    from paper_forge.compiler import load_project_config
    from paper_forge.renderers import render_pdf

    try:
        config = load_project_config(args.config)
        base_dir = Path(args.config).parent.resolve()
        input_md = base_dir / config["output"]

        if not input_md.exists():
            print(
                f"ERROR: Compiled manuscript not found at {input_md}. "
                "Run 'paper-forge compile' first.",
                file=sys.stderr,
            )
            return 1

        output_pdf = input_md.with_suffix(".pdf")
        if args.output:
            output_pdf = Path(args.output)

        # Gather render options from config
        render_opts = config.get("render", {})

        result_path = render_pdf(
            input_md,
            output_pdf,
            options=render_opts,
            project_dir=base_dir,
        )
        print(f"  PDF written to {result_path}")
        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="paper-forge",
        description="A framework for reproducible scientific paper writing from code.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new paper-forge project",
    )
    init_parser.add_argument(
        "dir",
        nargs="?",
        default=".",
        help="Directory to create the project in (default: current directory)",
    )

    # adopt
    adopt_parser = subparsers.add_parser(
        "adopt",
        help="Set up paper-forge around a manuscript that already exists",
    )
    adopt_parser.add_argument("dir", nargs="?", default=".", help="Project directory (default: .)")
    adopt_parser.add_argument(
        "--manuscript", default=None, help="The paper, if auto-detection picks the wrong file"
    )
    adopt_parser.add_argument("--name", default=None, help="Project name (default: directory name)")
    adopt_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be written, and write nothing"
    )

    # baseline
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Check the compiled manuscript still says what it said when adopted",
    )
    baseline_parser.add_argument(
        "--config", default="project.yaml", help="Path to project.yaml (default: project.yaml)"
    )
    baseline_parser.add_argument(
        "--record", action="store_true", help="Record a new baseline instead of comparing"
    )
    baseline_parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero when numbers have drifted"
    )

    # compile
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile manuscript (resolve placeholders)",
    )
    compile_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    compile_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (non-zero exit) if any placeholder is unresolved, instead of "
        "leaving it in the output and warning.",
    )

    # check
    check_parser = subparsers.add_parser(
        "check",
        help="Validate placeholders and guard against hardcoded numeric literals",
    )
    check_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    check_parser.add_argument(
        "--strict-literals",
        action="store_true",
        help="Treat hardcoded numeric literals in the template as errors "
        "(non-zero exit), not just warnings. Also settable via 'literals.enforce' "
        "in project.yaml.",
    )
    check_parser.add_argument(
        "--no-literals",
        action="store_true",
        help="Skip the numeric-literal guard entirely.",
    )
    check_parser.add_argument(
        "--strict-claims",
        action="store_true",
        help="Treat statistical verdicts asserted in template prose as errors "
        "(non-zero exit), not just warnings. Also settable via 'claims.enforce' "
        "in project.yaml.",
    )
    check_parser.add_argument(
        "--no-claims",
        action="store_true",
        help="Skip the verdict-claim guard entirely.",
    )
    check_parser.add_argument(
        "--strict-refs",
        action="store_true",
        help="Treat unresolvable citation keys as errors (non-zero exit), not just "
        "warnings. Also settable via 'citations.enforce' in project.yaml.",
    )
    check_parser.add_argument(
        "--no-refs",
        action="store_true",
        help="Skip the citation guard entirely.",
    )
    check_parser.add_argument(
        "--strict-units",
        action="store_true",
        help="Treat verdicts stated outright in a result unit as errors (non-zero exit), "
        "not just warnings. Also settable via 'unit_verdicts.enforce' in project.yaml.",
    )
    check_parser.add_argument(
        "--no-units",
        action="store_true",
        help="Skip the frozen-verdict guard entirely.",
    )

    # check-refs
    check_refs_parser = subparsers.add_parser(
        "check-refs",
        help="Cross-check citations against the bibliography and report coverage",
    )
    check_refs_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    check_refs_parser.add_argument(
        "--bib",
        action="append",
        default=None,
        help="Bibliography file to check against (repeatable). Overrides project.yaml "
        "and the manuscript front-matter.",
    )
    check_refs_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unresolvable citation keys as errors (non-zero exit).",
    )

    # verify-bib
    verify_bib_parser = subparsers.add_parser(
        "verify-bib",
        help="Record bibliography files as human-verified (writes bibliography.lock)",
    )
    verify_bib_parser.add_argument(
        "files",
        nargs="*",
        help="Bibliography files to verify (default: the project's configured bibliography)",
    )
    verify_bib_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    verify_bib_parser.add_argument(
        "--note",
        default=None,
        help="What you actually checked, recorded in the lock (e.g. 'DOIs spot-checked')",
    )

    # tokens
    tokens_parser = subparsers.add_parser(
        "tokens",
        help="Print the reference token for every bibliography entry (hand this to a writer)",
    )
    tokens_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    tokens_parser.add_argument(
        "--bib",
        action="append",
        default=None,
        help="Bibliography file to read (repeatable). Overrides project.yaml.",
    )
    tokens_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format (default: table)",
    )

    # check-rqs
    check_rqs_parser = subparsers.add_parser(
        "check-rqs",
        help="Check that every result unit serves a declared research question",
    )
    check_rqs_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )

    # gate
    gate_parser = subparsers.add_parser(
        "gate",
        help="Run the consistency gate (strict compile + literal, verdict and citation "
        "guards + check-rqs)",
    )
    gate_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )

    # pdf
    pdf_parser = subparsers.add_parser(
        "pdf",
        help="Render compiled markdown to PDF",
    )
    pdf_parser.add_argument(
        "--config",
        default="project.yaml",
        help="Path to project.yaml (default: project.yaml)",
    )
    pdf_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output PDF path (default: same stem as compiled markdown)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for the paper-forge CLI.

    Args:
        argv: Command line arguments. Uses sys.argv if None.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handlers = {
        "init": _cmd_init,
        "adopt": _cmd_adopt,
        "baseline": _cmd_baseline,
        "compile": _cmd_compile,
        "check": _cmd_check,
        "check-refs": _cmd_check_refs,
        "tokens": _cmd_tokens,
        "verify-bib": _cmd_verify_bib,
        "check-rqs": _cmd_check_rqs,
        "gate": _cmd_gate,
        "pdf": _cmd_pdf,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
