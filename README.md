# paper-forge 🔬📄

**Reproducible scientific paper writing from code.**

paper-forge eliminates transcription errors in scientific manuscripts by generating
every number, p-value, and statistical interpretation directly from analysis code.
Write your analysis once, and the manuscript stays in sync forever.

---

## The Problem

Scientific papers are full of numbers: sample sizes, means, p-values, effect sizes.
These numbers originate in analysis scripts but are manually copied into manuscripts.
This manual transcription causes errors — Nuijten et al. (2016) found that roughly
half of 250,000+ published psychology papers contained at least one inconsistent
p-value, and about 1 in 8 had errors severe enough to change the statistical
conclusion (Nuijten et al., "The prevalence of statistical reporting errors in
psychology," *Behavior Research Methods*, 2016).

## The Solution

paper-forge introduces a **4-layer architecture** that connects analysis code
directly to manuscript text:

```
┌──────────────────────────────────────────────────────────┐
│  Layer 4: PDF Output                                     │
│  ← pandoc renders the compiled markdown                  │
├──────────────────────────────────────────────────────────┤
│  Layer 3: Compiled Manuscript    (manuscript.md)         │
│  ← compiler fills placeholders with formatted values     │
├──────────────────────────────────────────────────────────┤
│  Layer 2: Manuscript Template    (manuscript_template.md)│
│  ← you write prose with {{prefix.key:formatter}} slots   │
├──────────────────────────────────────────────────────────┤
│  Layer 1: Result Units           (NN_name.py → .json)    │
│  ← Python scripts that run stats and emit JSON           │
└──────────────────────────────────────────────────────────┘
```

**You never type a number into your manuscript.** Instead, you write:

```markdown
We tested {{pop.n_total:int}} participants. The treatment group scored
significantly higher (U = {{pop.u_stat:fmt1}}, {{pop.main_p:p}},
r = {{pop.effect_size:r}}). {{pop.main_interp}}
```

And paper-forge compiles it to:

> We tested 87 participants. The treatment group scored significantly higher
> (U = 1,312.0, p = .002, r = .31). The difference was statistically
> significant, providing clear evidence for a treatment effect.

---

## Quickstart

### 1. Install

```bash
# Install paper-forge (requires Python 3.10+)
uv pip install paper-forge

# Or with statistical helpers:
uv pip install "paper-forge[stats]"
```

### 2. Initialize a Project

```bash
paper-forge init my-paper
cd my-paper
```

This creates:
```
my-paper/
├── project.yaml                  # Configuration
├── Makefile                      # Build automation
├── AGENT.md                      # AI agent instructions
├── .gitignore
├── manuscript/
│   ├── manuscript_template.md    # Your template (edit this)
│   ├── results/                  # JSON outputs land here
│   └── figures/                  # Generated figures
├── scripts/
│   └── result_units/
│       ├── __init__.py
│       └── 01_example.py         # Example result unit
└── tests/
    └── test_example.py
```

### 3. Write a Result Unit

Result units are Python scripts that run analyses and save JSON:

```python
#!/usr/bin/env python3
"""01_example — My first analysis."""
from pathlib import Path
import numpy as np
from scipy import stats
from paper_forge.result_unit import save_results

RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"

def main():
    # Load or generate data
    data_a = np.random.default_rng(42).normal(10, 2, 50)
    data_b = np.random.default_rng(42).normal(12, 2, 50)

    # Run statistics
    u, p = stats.mannwhitneyu(data_a, data_b, alternative="two-sided")
    r = 1 - (2 * u) / (len(data_a) * len(data_b))

    # Build results (flat dict of raw values + interpretation text)
    results = {
        "n_total": len(data_a) + len(data_b),
        "u_stat": float(u),
        "main_p": float(p),
        "effect_size": float(r),
        "main_interp": "Significant difference." if p < 0.05 else "No difference.",
    }

    # Git provenance + environment are captured automatically.
    # rq= links this unit to a declared research question (see "Research Questions").
    save_results("01_example", results, output_dir=RESULTS_DIR, rq="RQ1")

if __name__ == "__main__":
    main()
```

### 4. Write the Manuscript Template

In `manuscript/manuscript_template.md`, use `{{prefix.key:formatter}}` placeholders:

```markdown
---
title: "My Paper"
---

# Results

We analyzed {{ex.n_total:int}} observations.
The Mann–Whitney U test was significant
(U = {{ex.u_stat:fmt1}}, {{ex.main_p:p}}, r = {{ex.effect_size:r}}).
{{ex.main_interp}}
```

### 5. Configure the Prefix Map

In `project.yaml`, map each result unit to its placeholder prefix:

```yaml
result_units:
  prefix_map:
    "01_example": "ex"
```

### 6. Compile and Render

```bash
make units     # Run all result units → JSON files
make compile   # Fill placeholders → manuscript.md
make pdf       # Render → manuscript.pdf

# Or do it all at once:
make pipeline
```

---

## Placeholder Syntax Reference

```
{{prefix.key}}            Raw value, no formatting
{{prefix.key:int}}        Integer with thousands separator → 1,234
{{prefix.key:fmt1}}       1 decimal place → 12.3
{{prefix.key:fmt2}}       2 decimal places → 12.34
{{prefix.key:fmt3}}       3 decimal places → 12.345
{{prefix.key:r}}          Correlation/effect size → .312
{{prefix.key:p}}          P-value (APA style) → p = .023 or p < .001
{{prefix.key:pct}}        Percentage, 1 decimal → 45.2%
{{prefix.key:pct0}}       Percentage, whole number → 45%
```

### Rules
- `prefix` comes from `project.yaml`'s `prefix_map`
- `key` is a key in the result unit's JSON output
- `:formatter` is optional — without it, the raw value is inserted
- Text values (e.g., interpretation strings) need no formatter

---

## Built-in Formatters Reference

| Formatter | Aliases | Input | Output | Notes |
|-----------|---------|-------|--------|-------|
| `int` | | `1234` | `1,234` | Rounded, thousands separator |
| `f0` | `fmt0`, `float0` | `42.7` | `43` | 0 decimals |
| `f1` | `fmt1`, `float1` | `12.345` | `12.3` | 1 decimal place |
| `f2` | `fmt2`, `float2` | `12.345` | `12.35` | 2 decimal places |
| `f3` | `fmt3`, `float3` | `12.3456` | `12.346` | 3 decimal places |
| `r` | | `-0.456` | `−0.46` | Signed, 2 decimals, Unicode/ASCII minus |
| `p` | | `0.0234` | `0.023` | APA p-value; strips trailing zeros |
| `p` | | `3.8e-4` | `3.8×10⁻⁴` | Scientific notation (Unicode or LaTeX) |
| `stars` | `p_stars` | `0.003` | `**` | Significance stars (`***`/`**`/`*`/`n.s.`) |
| `pct` | | `0.452` | `45.2%` | ×100, 1 decimal |
| `pct0` | | `0.368` | `37%` | ×100, whole number |
| `min` | | `150` | `2.5 min` | Seconds → minutes |
| `hr` | | `5400` | `1.5 hr` | Seconds → hours |
| `raw` | | `anything` | `anything` | Default when no formatter given |

### Render Modes

paper-forge auto-detects whether to use **Unicode** or **LaTeX** formatting
based on your rendering engine. If your `project.yaml` includes
`--pdf-engine=xelatex` (or similar LaTeX engine):

- Small p-values produce `3.8 \times 10^{-4}` instead of `3.8×10⁻⁴`
- Effect sizes use ASCII minus (`-0.45`) instead of Unicode minus (`−0.45`)

Formatters **do not** add `$...$` delimiters — you control math mode in the
template as usual:

```markdown
$r = {{stats.corr:r}}$           →  $r = -0.45$
$p = {{stats.p_value:p}}$        →  $p = 3.8 \times 10^{-4}$
```

You can also set the mode manually:
```python
from paper_forge import set_render_mode
set_render_mode("latex")   # or "unicode" (default)
```

### Gotcha: `:r` Sign Characters

The `:r` formatter adds `+` for positive values by default. Don't also add
a sign in your template text:

```markdown
✅  $r = {{stats.corr:r}}$       →  $r = +0.32$
❌  $r = +{{stats.corr:r}}$      →  $r = ++0.32$
```

---

## Interpretation Engine

The interpretation engine generates natural-language text from statistical results.
Instead of the compiler generating prose, **result units emit interpretation text
as string values in their JSON output**. This keeps interpretation logic close to
the analysis code.

### Pattern

In your result unit:
```python
if p < 0.001:
    main_interp = "The effect was highly significant (p < .001)."
elif p < 0.05:
    main_interp = f"The effect was significant (p = {p:.3f})."
else:
    main_interp = "No significant effect was observed."

results["main_interp"] = main_interp
```

In your template:
```markdown
{{ex.main_interp}}
```

### Why This Approach?

- **Interpretation is a research decision** — it belongs with the analysis, not the compiler
- **Context matters** — the same p-value means different things in different analyses
- **Flexibility** — you can write any text, not just canned phrases
- **Traceability** — `git blame` on the result unit shows who wrote the interpretation

---

## Reproducibility Guardrails

paper-forge doesn't just *let* you source every number from code — it **checks** that you did.

`paper-forge check` scans the **template** for hardcoded numbers that should have come from
a result unit:

```bash
paper-forge check                    # placeholders + literal guard (literals are warnings)
paper-forge check --strict-literals  # hardcoded literals become errors (non-zero exit)
paper-forge check --no-literals      # skip the literal guard entirely
```

Digits inside placeholders, fenced code, citations (`[12]`), and section numbers are ignored.
For a number that genuinely belongs in prose (an order in a definition, a fixed axis label),
mark it with an inline escape hatch that names the reason:

```markdown
We fit an AR(1) baseline. <!-- pf-allow-literal: AR-order notation -->
```

The compiler **strips these directives** from the compiled output, so they never reach the
PDF. Set defaults in `project.yaml`:

```yaml
literals:
  enforce: true      # treat literals as errors (same as --strict-literals)
  allow:             # substrings always permitted in the template
    - "95%"
```

This is what turns *"numbers → prose, never the reverse"* from a guideline into a gate.

---

## Research Questions

Every result unit should exist to answer a **declared research question**. paper-forge makes
that link explicit and enforceable, which bounds how far an analysis can sprawl.

Declare your questions in `manuscript/research_questions.md`:

```markdown
## RQ-1 — Does the treatment reduce the outcome?
- **question:** Does treatment X lower outcome Y relative to control?
- **status:** answered
- **units:** 01_demographics, 02_primary
```

Statuses are `open` · `answered` · `candidate` · `dropped`. Descriptive/setup units that
characterise the data rather than answer a question declare `rq="methods"`.

Link each unit to its question in `save_results`, then enforce the mapping:

```python
save_results("02_primary", results, output_dir=RESULTS_DIR, rq="RQ-1")
```
```bash
paper-forge check-rqs
```

`check-rqs` fails if a unit serves no declared question, points at an unknown RQ, or if an
`open`/`answered` question has no backing units. Because the set of questions is the natural
ceiling on analysis breadth, *growing* the analysis (admit a new `candidate` question) or
*narrowing* it (mark one `dropped`) becomes a deliberate, reviewable edit to this one file —
not scope creep. Point paper-forge at the registry with `research_questions:` in
`project.yaml` (defaults to `manuscript/research_questions.md`).

---

## Project Configuration (`project.yaml`)

```yaml
project:
  name: "my-paper"
  title: "Full Paper Title"

manuscript:
  template: "manuscript/manuscript_template.md"
  output_md: "manuscript/manuscript.md"
  output_pdf: "manuscript/manuscript.pdf"
  results_dir: "manuscript/results"
  figures_dir: "manuscript/figures"

result_units:
  prefix_map:
    "01_demographics": "demo"
    "02_primary": "pri"
    "03_secondary": "sec"

# Where the research-question registry lives (default shown).
research_questions: "manuscript/research_questions.md"

# Numeric-literal guard (optional; defaults shown).
literals:
  enforce: false          # true = hardcoded literals fail `check` (like --strict-literals)
  allow: []               # substrings always permitted in the template

execution:
  python: "uv run python"

rendering:
  engine: "pandoc"
  pandoc_args:
    - "--pdf-engine=xelatex"
    - "--citeproc"
    - "--number-sections"
```

---

## Agent Workflows

paper-forge ships with 5 agent workflows for AI-assisted paper writing:

| Command | Workflow | Description |
|---------|----------|-------------|
| `/scaffold` | [scaffold_paper.md](workflows/scaffold_paper.md) | Set up a new paper project |
| `/write_unit` | [write_result_unit.md](workflows/write_result_unit.md) | Create a result unit from a data description |
| `/draft_template` | [draft_template.md](workflows/draft_template.md) | Generate manuscript template from results |
| `/compile` | [compile_and_review.md](workflows/compile_and_review.md) | Run pipeline and review |
| `/iterate` | [iterate_manuscript.md](workflows/iterate_manuscript.md) | Refine based on feedback |

Each workflow is a step-by-step guide that an AI agent (or human) can follow
to complete a specific task in the paper-writing process.

---

## AI Review Loop (runs inside Claude Code)

paper-forge ships a closed-loop reviewer that runs **entirely on Claude Code subagents** —
no external LLM, no API keys. The referee is a subagent; the gate is paper-forge itself
(deterministic Python). The assets live under `templates/claude/` (copy into your project's
`.claude/`):

| Command | Agent | What it does |
|---------|-------|--------------|
| `/paper-review` | `manuscript-reviewer` | Compiles the paper, scores it against `manuscript/review/rubric.md`, and returns ranked findings — every numeric claim **verified against the result JSONs**, so the referee can't win on a hallucinated discrepancy. Read-only. |
| `/paper-analyze` | `data-analyst` | Turns review findings into **bounded, gate-verified** changes to the *result units* — never prose, never unbounded new work. |

### Scope control (default-deny on expansion)

Reviewers always ask for more analysis. `/paper-analyze` triages each finding and only acts
within the research-question registry and the analysis charter (`manuscript/review/charter.md`):

| Tier | What it is | Default action |
|------|------------|----------------|
| **fix** | correct a computation the paper already reports | auto: run the analyst |
| **strengthen** | add rigor (CI/test/sensitivity) to an existing claim | ask first, then run |
| **deepen** | an unknown the *existing data* can answer, no current RQ | propose a `candidate` RQ for a human to admit |
| **focus** | a claim/RQ is weak or under-supported | propose narrowing/dropping the RQ |
| **expand** | needs *new data* / features / models | propose a rebuttal note only — nothing runs |

Every candidate change must pass the gate (`check --strict-literals` + `compile` +
`check-rqs`), and the analyst edits result units only — so a number changes only through
reproducible code. See [`docs/review_loop_build_plan.md`](docs/review_loop_build_plan.md)
for the full design and milestones.

---

## Example Project

The `examples/bee_sleep_dance/` directory contains a complete working example
based on a fictional study of sleep deprivation effects on honeybee dance
communication.

```bash
cd examples/bee_sleep_dance
make pipeline   # Run units → compile → PDF
```

The example includes:
- Two result units (population analysis + temporal analysis)
- Pre-generated JSON results (compiles without running scripts)
- A complete manuscript template with 30+ placeholders

---

## Command-Line Interface

The Makefile targets wrap the `paper-forge` CLI, which you can also call directly:

| Command | Description |
|---------|-------------|
| `paper-forge init [dir]` | Scaffold a new project |
| `paper-forge compile [--strict]` | Fill placeholders → compiled markdown |
| `paper-forge check [--strict-literals] [--no-literals]` | Validate placeholders + numeric-literal guard |
| `paper-forge check-rqs` | Verify every result unit serves a declared research question |
| `paper-forge pdf [-o out.pdf]` | Render compiled markdown to PDF |

All commands accept `--config PATH` (default `project.yaml`).

---

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make all` | Compile + render PDF (default) |
| `make units` | Run all result unit scripts |
| `make compile` | Fill placeholders in template |
| `make check` | Validate placeholders against results |
| `make pdf` | Render compiled markdown to PDF |
| `make pipeline` | Units + compile + PDF |
| `make test` | Run pytest |
| `make lint` | Run ruff linter |
| `make format` | Auto-format code with ruff |
| `make clean` | Remove generated files |

---

## Design Philosophy

### Numbers → Prose, Never the Reverse

The single most important rule: **every number in the manuscript must originate
from a result unit's JSON output**. If you catch yourself typing `n = 42` in
the template, stop and add it to a result unit instead. `paper-forge check
--strict-literals` enforces this mechanically (see [Reproducibility
Guardrails](#reproducibility-guardrails)).

### One Result Unit, One JSON

Keep analyses modular. Each result unit answers one question and produces one
JSON file. This makes it easy to re-run individual analyses and track which
numbers come from where.

### Interpretation Lives with Analysis

Statistical interpretation (e.g., "the effect was significant") is generated
in the result unit, not the template. This keeps the judgment call close to
the statistical test that produced it.

### Git Provenance

Every result JSON includes metadata about which git commit and script version
produced it. This creates an audit trail from any number in the paper back to
the exact code that computed it.

### Every Result Unit Serves a Research Question

Each unit declares the question it answers (`rq=` in `save_results`), and
`paper-forge check-rqs` enforces the mapping. The set of research questions is
the natural bound on how far an analysis can grow (see [Research
Questions](#research-questions)).

---

## Contributing

paper-forge is developed at Freie Universität Berlin. Contributions are welcome!

```bash
# Clone and set up development environment
git clone <repo-url>
cd paper-forge
uv sync
uv run pytest
```

See [AGENT.md](AGENT.md) for detailed development instructions.

---

## License

MIT
