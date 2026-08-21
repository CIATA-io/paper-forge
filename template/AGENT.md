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

### The same rule applies to verdicts

A *verdict* is any claim whose truth depends on a statistic: "significant",
"does not differ", "predicts", "stronger than". These are more dangerous than
hardcoded numbers, because they contain no digits — they survive a clean compile
and the literal guard, then quietly contradict the data the next time you change
a threshold or add a season.

- ✅ `Dance {{interp.dance_sleep}} night sleep (p = {{temp.wb_p:p}}).`
- ❌ `Dance significantly predicts night sleep (p = {{temp.wb_p:p}}).`

The second one keeps updating the p-value while the word "significantly" stays
frozen at whatever was true the day it was typed.

Verdicts are resolved by the **interpretation engine** — declare a rule in
`interpretations.yaml` and reference it as `{{interp.<output_key>}}`. `paper-forge
check` warns on verdicts found in template prose; `paper-forge gate` fails on them.

paper-forge *also* lets a result unit emit the interpretation itself, and for a
human writing the unit that is a fine choice — `if p < .05: interp = "..."` is
re-decided from the data on every run (see the README). **In this project the rules
engine is the rule for agent-authored units**. An agent that reads `p = .003` and
writes `interp = "The effect was significant."` has frozen a verdict that is
indistinguishable from the branch version in the result JSON. The **frozen-verdict
guard** catches exactly that — it reads the unit's source and flags a verdict string
that is not inside a branch — but a YAML rule cannot be written that way at all: the
branch *is* the rule, so the mistake becomes unavailable rather than merely caught.

Built-in rule functions are `correlation_effect`, `correlation_qualifier`,
`comparison` and `significance_stars`. For a verdict they cannot express — a
multi-branch directionality summary, a Title Case variant for a heading — write a
function instead of writing prose:

```python
# scripts/interp_functions.py
def register(engine):
    engine.register_function("directionality", directionality)
```

```yaml
# project.yaml
interpretation_functions: scripts/interp_functions.py
```

Claims about *published work* are static by nature and are exempt — the guard
skips any sentence carrying a citation. In a project with a `.bib`, "carrying a
citation" means **citing a key that resolves**: `\citep{klein2010}` or `[@klein2010]`
where `klein2010` is really in the bibliography. Typing `(Klein et al. 2010)` into
the prose does *not* exempt anything — it cites nothing, citeproc ignores it, and it
never reaches the reference list. For anything else that is genuinely fixed,
mark it explicitly:

```markdown
Colonies were housed at 34 °C throughout. <!-- pf-allow-claim: protocol constant -->
```

### The same rule applies to citations

A citation is the one element that looks equally plausible whether or not it exists.
`\citep{smith2019}` compiles and reads well even when nothing called `smith2019` is in
the bibliography — so **never write a cite key you have not seen in the `.bib` file**.
If a claim needs a source you do not have, leave a marker and ask:

```markdown
Sleep loss degrades waggle precision. <!-- TODO(cite): need a source -->
```

This matters twice over, because the verdict-claim guard exempts sentences that cite published
work — a claim about someone else's result is static by nature. That exemption now requires
a key that **resolves**, so an invented citation no longer buys it: the reference is
reported as missing *and* the verdict attached to it still gets flagged.

`paper-forge check-refs` cross-checks every cite key against the bibliography, reports
which entries the manuscript never cites, and flags author-year attributions typed as prose
(`unkeyed-attribution`); `paper-forge gate` fails on both.

### Citing with reference tokens

If the project uses reference tokens, run `paper-forge tokens` and **copy** the token
for the entry you mean:

```markdown
Swarms can act as reservoirs [ref:2425b69172b7].
```

A token is derived from the bibliography entry — you cannot compute or guess one. If
you find yourself composing a token, stop: it will not resolve, and `gate` will report
it as an invented citation. If the source you need is not in the token table, it is not
in the bibliography; say so rather than inventing a citation.

`compile` turns each token into a real citation, so the rendered PDF is unaffected.

Both key syntaxes are also recognised — LaTeX (`\cite`, `\citep`, `\textcite`, …) and
pandoc (`[@key]`, `[-@key; @other]`, bare `@key`). For an `@` that is not a citation:

```markdown
Follow @nature for updates. <!-- pf-allow-cite: social handle -->
```

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
configured, formatters produce LaTeX-compatible output (ASCII minus, `\times`
notation) instead of Unicode (`−`, `×10⁻⁴`).

Formatters **do not** add `$...$` delimiters — you control math mode in the
template:

```markdown
$r = {{stats.corr:r}}$         →  $r = -0.45$
$p = {{stats.p_value:p}}$      →  $p = 3.8 \times 10^{-4}$
```

## Workflow Commands

```bash
make units       # Run all result unit scripts
make compile     # Fill placeholders → manuscript.md
make check       # Validate placeholders, literals, verdicts, citations
make check-refs  # Cross-check citations against bibliography; report coverage
make tokens      # Print the reference-token table (copy tokens from here)
make verify-bib  # Record a .bib as human-verified (writes bibliography.lock)
make pdf         # Render manuscript.md → manuscript.pdf
make all         # compile + pdf
make pipeline    # units + compile + pdf
make test        # Run tests
make lint        # Run ruff linter
make clean       # Remove generated files
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
2. **Never hardcode verdicts** in the manuscript template. Any claim that depends on
   a statistic comes from `{{interp.*}}` — see "The same rule applies to verdicts".
3. **Never let observed values decide the wording.** You will read result JSONs while
   drafting. Use them to learn which *keys* exist, never to pick which claim to write.
   If you would have to re-word a sentence when a p-value crosses 0.05, that sentence
   needs an interpretation rule.
4. **Never modify `manuscript.md` directly** — it is generated. Edit the template.
5. **Never modify JSON files by hand** — they are generated by result units.
6. **Result units you write emit numbers, not prose.** No "significant"/"not significant"
   strings in a result unit *you* author — put that decision in `interpretations.yaml`.
   paper-forge does allow a unit to *derive* the phrase by branching on the statistic, and a
   human may write it that way (README option 1); the rule is stricter for you because a
   verdict you state outright is one you chose by reading the data. `make check` runs the
   frozen-verdict guard over the units and `paper-forge gate` fails on it.
7. **Never invent a cite key or a reference token.** Cite only keys that exist in the
   project's `.bib`, or tokens copied verbatim from `paper-forge tokens`.
8. **You may create a new .bib file** as a draft (e.g., from a deep-research pass).
   Expect `make check-refs` to report every citation into it as `unverified-entry` — that
   is normal working state. A human clears the finding by running `make verify-bib`.
9. **Never edit a verified .bib.** `bibliography.lock` records the digest of each
   human-verified file. Appending even one entry changes the digest and produces a
   `modified-bibliography` finding that fails `gate` unconditionally, in every mode. If you
   need to add an entry, create a separate new draft file and cite from there; ask the
   human to merge and re-verify.
10. **Always run `make check`** after modifying the template to catch missing placeholders,
    hardcoded numbers, unbacked verdicts, and citations that resolve to nothing.
11. **Always run `make compile`** after modifying result units to update the manuscript.
12. **Test result units** with `make test` before compiling.
13. **One JSON per result unit** — keep analyses modular and focused.
