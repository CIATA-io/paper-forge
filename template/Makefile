# paper-forge project Makefile
# ============================================================
# Usage:
#   make compile    — compile manuscript (fill placeholders)
#   make check      — run placeholder, literal, verdict, and citation guards
#   make check-refs — cross-check citations against bibliography
#   make tokens     — print the reference-token table
#   make verify-bib — record the bibliography as human-verified
#   make pdf        — render compiled manuscript to PDF
#   make all        — compile + pdf
#   make units      — run all result units
#   make test       — run tests
#   make lint       — run ruff linter
#   make clean      — remove generated files
# ============================================================

PYTHON ?= uv run python
PAPER_FORGE ?= uv run paper-forge

.PHONY: all compile check check-refs tokens verify-bib pdf units test lint clean help

# Default target
all: compile pdf

# Run all result unit scripts
units:
	@bash scripts/run_all_units.sh

# Compile manuscript: fill placeholders from result JSONs
compile:
	$(PAPER_FORGE) compile

# Validate placeholders, literals, verdicts, and citations
check:
	$(PAPER_FORGE) check

# Cross-check every citation key against the bibliography; report coverage
check-refs:
	$(PAPER_FORGE) check-refs

# Print the reference-token table (hand to a writer before they cite)
tokens:
	$(PAPER_FORGE) tokens

# Record the bibliography as human-verified; writes bibliography.lock (commit it)
verify-bib:
	$(PAPER_FORGE) verify-bib

# Render the compiled markdown to PDF via pandoc
pdf:
	$(PAPER_FORGE) pdf

# Run the full pipeline: units → compile → pdf
pipeline: units compile pdf

# Run tests
test:
	$(PYTHON) -m pytest tests/ -v

# Lint with ruff
lint:
	uv run ruff check scripts/ tests/
	uv run ruff format --check scripts/ tests/

# Format code
format:
	uv run ruff check --fix scripts/ tests/
	uv run ruff format scripts/ tests/

# Remove generated / compiled files
clean:
	rm -f manuscript/manuscript.md
	rm -f manuscript/manuscript.pdf
	rm -f manuscript/results/*.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Show help
help:
	@echo "Available targets:"
	@echo "  make all       — compile + pdf (default)"
	@echo "  make units     — run all result unit scripts"
	@echo "  make compile   — fill placeholders in manuscript template"
	@echo "  make check      — validate placeholders, literals, verdicts, citations"
	@echo "  make check-refs — cross-check citations against bibliography"
	@echo "  make tokens     — print the reference-token table"
	@echo "  make verify-bib — record the bibliography as human-verified"
	@echo "  make pdf        — render manuscript to PDF"
	@echo "  make pipeline  — units → compile → pdf"
	@echo "  make test      — run pytest"
	@echo "  make lint      — run ruff linter"
	@echo "  make format    — auto-format code with ruff"
	@echo "  make clean     — remove generated files"
