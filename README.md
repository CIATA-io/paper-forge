# paper-forge

A framework for reproducible scientific paper writing from code.

## Overview

paper-forge connects your analysis scripts to your manuscript. Write result units
that output statistics as JSON, reference them with `{{prefix.key:formatter}}`
placeholders in your Markdown manuscript, and let paper-forge compile everything
into a polished document with full git provenance.

## Installation

```bash
uv pip install paper-forge
# or with statistical helpers:
uv pip install "paper-forge[stats]"
```

## Quickstart

```bash
# Scaffold a new project
paper-forge init my-paper

# Run your analysis scripts, then compile
paper-forge compile --config project.yaml

# Check for unresolved placeholders
paper-forge check --config project.yaml

# Render PDF
paper-forge pdf --config project.yaml
```

## How it works

1. **Result units** — Python scripts that call `save_results()` to output JSON
   files with raw statistics and git provenance.
2. **Manuscript template** — Markdown with `{{prefix.key:formatter}}` placeholders.
3. **Compiler** — Reads all result JSONs, resolves placeholders, applies formatters
   and interpretation rules, writes final markdown.
4. **Renderer** — Converts compiled markdown to PDF via pandoc.

## License

MIT
