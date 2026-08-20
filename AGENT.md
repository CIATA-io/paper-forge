# AGENT.md — paper-forge Framework Development Guide

> This file is for developers working on the paper-forge framework itself.
> For instructions on using paper-forge in a paper project, see `template/AGENT.md`.

## Overview

paper-forge is a Python framework for reproducible scientific paper writing.
It connects analysis scripts to manuscripts via JSON intermediaries and
placeholder-based templating.

## Repository Structure

```
paper-forge/
├── paper_forge/                  # Core Python package
│   ├── __init__.py
│   ├── cli.py                    # argparse CLI (init/compile/check/check-refs/check-rqs/pdf)
│   ├── compiler.py               # project.yaml loader + placeholder compilation
│   ├── formatters.py             # Number formatters (p, r, int, fmt2, pct, pct0, …)
│   ├── literals.py               # Numeric-literal guard (hardcoded-number detector)
│   ├── claims.py                 # Verdict-claim guard (hardcoded-verdict detector)
│   ├── citations.py              # Citation guard (bibtex parser + cite-key resolution/coverage)
│   ├── sentences.py              # Abbreviation-aware sentence segmentation (shared by guards)
│   ├── research_questions.py     # RQ registry parser + check-rqs enforcement
│   ├── interpretation.py         # Optional compile-time interpretation rules engine
│   ├── provenance.py             # Git provenance & environment capture
│   ├── result_unit.py            # save_results() / load_results()
│   ├── renderers/                # Pandoc PDF rendering
│   └── stats/                    # Statistical test wrappers
│
├── template/                     # Project template (copied by `paper-forge init`)
│   ├── project.yaml              # Example configuration
│   ├── interpretations.yaml      # Verdict rules → {{interp.*}} (worked example)
│   ├── Makefile                  # Build automation
│   ├── AGENT.md                  # User-facing agent instructions
│   ├── .gitignore
│   ├── manuscript/
│   │   ├── manuscript_template.md
│   │   ├── results/
│   │   └── figures/
│   ├── scripts/
│   │   └── result_units/
│   │       ├── __init__.py
│   │       └── 01_example.py
│   └── tests/
│       └── test_example.py
│
├── examples/                     # Working example projects
│   └── bee_sleep_dance/
│       ├── project.yaml
│       ├── Makefile
│       ├── scripts/result_units/
│       └── manuscript/
│
├── workflows/                    # Agent workflow files
│   ├── scaffold_paper.md         # /scaffold
│   ├── write_result_unit.md      # /write_unit
│   ├── draft_template.md         # /draft_template
│   ├── compile_and_review.md     # /compile
│   └── iterate_manuscript.md     # /iterate
│
├── tests/                        # Framework-level tests
├── pyproject.toml                # Package metadata & dependencies
├── README.md                     # User-facing documentation
└── AGENT.md                      # This file (dev guide)
```

## Architecture

### Core Modules (`paper_forge/`)

| Module | Purpose |
|--------|---------|
| `cli.py` | argparse CLI: `init`, `compile`, `check`, `check-refs`, `tokens`, `check-rqs`, `gate`, `pdf` |
| `compiler.py` | Loads `project.yaml`, reads JSONs, resolves `{{prefix.key:fmt}}` placeholders; strips `pf-allow-literal` directives from the output |
| `formatters.py` | Formatting functions (`fmt_p()`, `fmt_r()`, `fmt_int()`, `fmt_pct0()`, …) and the `FORMATTERS` registry |
| `literals.py` | Numeric-literal guard: flags hardcoded numbers in the template (`check --strict-literals`) |
| `claims.py` | Verdict-claim guard: flags statistical verdicts asserted in prose instead of resolved via `{{interp.*}}` (`check --strict-claims`). Exempts a sentence citing a **resolvable** key when `bib_keys` is supplied, citation-shaped prose otherwise, and `pf-allow-claim` lines |
| `sentences.py` | Abbreviation-aware sentence segmentation. Both guards need sentence granularity because manuscript markdown puts a paragraph on one line; kept separate so `claims.py` can depend on `citations.py` without a cycle |
| `citations.py` | Citation guard: a dependency-free BibTeX parser plus LaTeX/pandoc cite extraction; `check_citations()` reports unresolvable keys, duplicate keys and bibliography coverage (`check-refs`). Exposes `BibEntry` so a DOI verifier can be layered on top |
| `research_questions.py` | Parses the RQ registry; `check_research_questions()` powers `check-rqs` |
| `interpretation.py` | Optional `InterpretationEngine` — derives phrases from result values at compile time (enable via `interpretations:` in project.yaml). `load_function_plugin()` lets a project register its own verdict functions via `interpretation_functions:`; it must run before `load_rules()`, which rejects unknown function names |
| `provenance.py` | `get_git_provenance()` / `get_environment()` — git hash, dirty state, package list |
| `result_unit.py` | `save_results()` — writes JSON envelope (+ `rq`); `load_results()` — reads JSON |
| `renderers/` | Wraps pandoc to convert compiled markdown to PDF |
| `stats/` | Thin wrappers around scipy.stats with consistent output dicts |

### Data Flow

```
01_name.py → save_results() → results/01_name.json
                                       ↓
project.yaml → prefix_map → {"01_name": "pf"}
                                       ↓
template.md + results/*.json → compiler → manuscript.md → pandoc → manuscript.pdf
```

### Placeholder Resolution Algorithm

1. Load all JSON files from `results_dir`
2. Build a flat lookup: `{prefix}.{key}` → value
3. Regex scan template for `{{prefix.key}}` and `{{prefix.key:formatter}}`
4. For each match:
   - Look up the value
   - Apply the formatter (if specified)
   - Replace the placeholder with the formatted string
5. Report any unresolved placeholders as errors

## Development Setup

```bash
# Clone the repo
git clone <repo-url>
cd paper-forge

# Install in development mode
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check .
uv run ruff format --check .
```

## Testing Strategy

### Framework Tests (`tests/`)
- Test formatters with edge cases (negative values, zero, very small p-values)
- Test compiler with mock templates and JSON files
- Test config parsing with valid and invalid YAML
- Test checker finds missing and orphaned placeholders
- Test provenance captures git metadata

### Template Tests (`template/tests/`)
- These are example tests shipped to users
- They test result unit output structure and plausibility

### Example Tests
- The bee_sleep_dance example includes pre-generated JSONs
- CI should verify the example compiles successfully

## Key Design Decisions

### Flat Result Dicts
Result JSONs use flat key-value pairs (no nesting) so that placeholder syntax
stays simple: `{{prefix.key}}`. No need for dot-notation traversal.

### Formatters Are Pure Functions
Each formatter takes a single numeric value and returns a string.
They are stateless and have no side effects. This makes them easy to test.

### Interpretation as Data (with an optional rules engine)
The recommended pattern is that result units emit interpretation strings as JSON
values, keeping the research judgment (what does p < .05 mean here?) with the
analysis code. An optional compile-time rules engine (`interpretation.py`, enabled
via `interpretations:` in project.yaml) can also derive phrases from result values
for projects that prefer that. Either way, keep raw numbers out of interpretation
strings — the numeric-literal guard only scans the template, so numerals baked into
a string bypass it.

### Provenance is Automatic
`save_results()` always includes provenance metadata (git commit, branch, and
dirty state) plus environment info (Python version, platform, package versions).
Users don't need to remember to add it.

## Adding a New Formatter

1. Add the function to `paper_forge/formatters.py`:
   ```python
   def fmt_ci(value: tuple[float, float]) -> str:
       """Format a confidence interval."""
       return f"[{value[0]:.2f}, {value[1]:.2f}]"
   ```

2. Register it in the `FORMATTERS` dict in `formatters.py`

3. Add tests in `tests/test_formatters.py`

4. Document it in `README.md` (Formatters Reference table)

## Adding a New CLI Command

1. Add a `_cmd_<name>(args)` handler in `paper_forge/cli.py`, register a
   subparser in `build_parser()`, and wire it into the `handlers` dict:
   ```python
   def _cmd_my_command(args: argparse.Namespace) -> int:
       ...
       return 0
   # build_parser():  subparsers.add_parser("my-command", ...)
   # main():          handlers = {..., "my-command": _cmd_my_command}
   ```

2. Add tests in `tests/test_cli.py`

3. Expose it via a Makefile target and the CLI table in `README.md`

## Coding Standards

- **Python 3.10+** — use modern type hints (`str | None`, not `Optional[str]`)
- **pathlib** for all file operations (no `os.path`)
- **Type annotations** on all public functions
- **Docstrings** — Google style
- **Ruff** for linting and formatting
- **pytest** for testing
- **uv** for package management
