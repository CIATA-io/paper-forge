# AGENT.md — Project Architecture Guide

> This file describes the architecture of this paper-forge project.
> Customize it for your specific paper.

## Overview

This project uses **paper-forge** to produce a reproducible scientific manuscript.
Every number, p-value, and statistical interpretation in the paper is generated
from code — never typed by hand.

## The 4-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 4: PDF Output                                │
│  manuscript/manuscript.pdf                          │
│  ← pandoc renders compiled markdown to PDF          │
├─────────────────────────────────────────────────────┤
│  Layer 3: Compiled Manuscript                       │
│  manuscript/manuscript.md                           │
│  ← compiler fills placeholders from JSON results    │
├─────────────────────────────────────────────────────┤
│  Layer 2: Manuscript Template                       │
│  manuscript/manuscript_template.md                  │
│  ← markdown with {{prefix.key:formatter}} slots     │
├─────────────────────────────────────────────────────┤
│  Layer 1: Result Units                              │
│  scripts/result_units/NN_name.py → results/NN.json  │
│  ← Python scripts that compute stats & save JSON    │
└─────────────────────────────────────────────────────┘
```

## Key Principle: Numbers → Prose

**The only source of truth for any number in the paper is a result unit's JSON output.**

- ✅ `{{pop.n_total:int}}` — correct: number comes from code
- ❌ `We tested 127 bees` — wrong: hardcoded number will drift from data

If you need prose that depends on a statistical result (e.g., "significant" vs.
"not significant"), generate that text in the result unit and emit it as a
string value in the JSON.

## Result Units

Each result unit is a Python script in `scripts/result_units/` that:

1. Loads or generates data
2. Runs statistical analyses
3. Builds a flat dict of results (numbers + text)
4. Calls `save_results()` to write JSON with git provenance

### Naming Convention

Scripts are numbered: `01_population.py`, `02_temporal.py`, etc.
The number prefix determines execution order.

### Prefix Map

In `project.yaml`, each unit maps to a short prefix used in placeholders:

```yaml
result_units:
  prefix_map:
    "01_example": "ex"
```

This means `01_example.json` keys are referenced as `{{ex.key_name}}`.

### Known-Values Pattern

Not every result unit runs a live analysis. When values were computed externally
(e.g., on a remote server) and are stable, create a "constants" unit:

```python
#!/usr/bin/env python3
"""05_known_values — Values from external analysis."""
from pathlib import Path
from paper_forge.result_unit import save_results

REPO_ROOT = Path(__file__).resolve().parents[2]

def main() -> None:
    results = {
        "n_factors": 8,
        "strongest_r": -0.84,
        "icc": 0.56,
    }
    save_results(
        "05_known_values", results,
        output_dir=REPO_ROOT / "manuscript" / "results",
    )

if __name__ == "__main__":
    main()
```

This still gets git provenance and follows the same pipeline as computed units.

## Placeholder Syntax

```
{{prefix.key}}           — raw value, no formatting
{{prefix.key:int}}       — integer formatting (1,234)
{{prefix.key:fmt2}}      — 2 decimal places (1.23)
{{prefix.key:r}}         — correlation coefficient (.123)
{{prefix.key:p}}         — p-value (p = .023 or p < .001)
{{prefix.key:pct}}       — percentage (45.2%)
```

### Formatter Aliases

The following aliases are interchangeable:

| Canonical | Aliases |
|-----------|--------------------------------------|
| `f0` | `fmt0`, `float0` |
| `f1` | `fmt1`, `float1` |
| `f2` | `fmt2`, `float2` |
| `f3` | `fmt3`, `float3` |

### Gotcha: `:r` Formatter and Sign Characters

The `:r` formatter adds a `+` prefix for positive values by default.
If your template already includes a sign (e.g., `$r = +{{stats.r:r}}$`),
you'll get `++0.32`. Use one or the other:

- ✅ `$r = {{stats.r:r}}$` → `$r = +0.32$`
- ❌ `$r = +{{stats.r:r}}$` → `$r = ++0.32$`

### Render Modes

paper-forge auto-detects whether to use Unicode or LaTeX formatting based on
your `project.yaml` rendering engine. If `--pdf-engine=xelatex` (or similar) is
configured, small p-values will produce `$3.8 \times 10^{-4}$` (LaTeX math)
instead of `3.8×10⁻⁴` (Unicode superscripts).

## Workflow Commands

```bash
make units      # Run all result unit scripts
make compile    # Fill placeholders → manuscript.md
make check      # Validate all placeholders have values
make pdf        # Render manuscript.md → manuscript.pdf
make all        # compile + pdf
make pipeline   # units + compile + pdf
make test       # Run tests
make lint       # Run ruff linter
make clean      # Remove generated files
```

## Project Structure

```
project.yaml                     # Central configuration
manuscript/
  manuscript_template.md         # Template with placeholders
  manuscript.md                  # Compiled output (generated)
  manuscript.pdf                 # PDF output (generated)
  results/                       # JSON files from result units
  figures/                       # Generated figures
scripts/
  result_units/
    __init__.py                  # Shared imports
    01_example.py                # Result unit scripts
  run_all_units.sh               # Runner script
tests/
  test_example.py                # Tests for result units
Makefile                         # Build automation
```

## Rules for AI Agents

1. **Never hardcode numbers** in the manuscript template. Always use placeholders.
2. **Never modify `manuscript.md` directly** — it is generated. Edit the template.
3. **Never modify JSON files by hand** — they are generated by result units.
4. **Always run `make check`** after modifying the template to catch missing placeholders.
5. **Always run `make compile`** after modifying result units to update the manuscript.
6. **Test result units** with `make test` before compiling.
7. **One JSON per result unit** — keep analyses modular and focused.
