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
│   ├── cli.py                    # CLI entry point (paper-forge command)
│   ├── compiler.py               # Placeholder resolution & compilation
│   ├── config.py                 # project.yaml loader
│   ├── formatters.py             # Number formatters (p, r, int, fmt2, pct)
│   ├── provenance.py             # Git provenance & file hashing
│   ├── result_unit.py            # save_results() / load_results()
│   ├── checker.py                # Placeholder validation
│   ├── renderer.py               # Pandoc PDF rendering
│   └── stats.py                  # Statistical test wrappers
│
├── template/                     # Project template (copied by `paper-forge init`)
│   ├── project.yaml              # Example configuration
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
| `cli.py` | Click-based CLI: `init`, `compile`, `check`, `render` |
| `compiler.py` | Reads template, loads JSONs, resolves `{{prefix.key:fmt}}` placeholders |
| `config.py` | Parses `project.yaml`, validates config schema |
| `formatters.py` | Formatting functions: `fmt_p()`, `fmt_r()`, `fmt_int()`, etc. |
| `provenance.py` | `get_git_provenance()` — captures git hash, dirty state, script hash |
| `result_unit.py` | `save_results()` — writes JSON; `load_results()` — reads JSON |
| `checker.py` | Validates all template placeholders have corresponding result keys |
| `renderer.py` | Wraps pandoc to convert compiled markdown to PDF |
| `stats.py` | Thin wrappers around scipy.stats with consistent output dicts |

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

### Interpretation as Data
The compiler does not generate interpretation text. Instead, result units
emit interpretation strings as JSON values. This keeps the research
judgment (what does p < .05 mean in this context?) with the analysis code.

### Provenance is Automatic
`save_results()` always includes provenance metadata (git hash, dirty state,
script file hash). Users don't need to remember to add it.

## Adding a New Formatter

1. Add the function to `paper_forge/formatters.py`:
   ```python
   def fmt_ci(value: tuple[float, float]) -> str:
       """Format a confidence interval."""
       return f"[{value[0]:.2f}, {value[1]:.2f}]"
   ```

2. Register it in the `FORMATTERS` dict in `compiler.py`

3. Add tests in `tests/test_formatters.py`

4. Document it in `README.md` (Formatters Reference table)

## Adding a New CLI Command

1. Add the command function in `paper_forge/cli.py`:
   ```python
   @cli.command()
   @click.option("--config", default="project.yaml")
   def my_command(config):
       ...
   ```

2. Add tests in `tests/test_cli.py`

3. Add a Makefile target in `template/Makefile`

## Coding Standards

- **Python 3.10+** — use modern type hints (`str | None`, not `Optional[str]`)
- **pathlib** for all file operations (no `os.path`)
- **Type annotations** on all public functions
- **Docstrings** — Google style
- **Ruff** for linting and formatting
- **pytest** for testing
- **uv** for package management
