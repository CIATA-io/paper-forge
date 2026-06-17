# paper-forge project Makefile
# ============================================================
# Usage:
#   make compile   — compile manuscript (fill placeholders)
#   make check     — validate all placeholders are satisfied
#   make pdf       — render compiled manuscript to PDF
#   make all       — compile + pdf
#   make units     — run all result units
#   make test      — run tests
#   make lint      — run ruff linter
#   make clean     — remove generated files
# ============================================================

PYTHON ?= uv run python
PAPER_FORGE ?= uv run paper-forge

.PHONY: all compile check pdf units test lint clean help

# Default target
all: compile pdf

# Run all result unit scripts
units:
	@bash scripts/run_all_units.sh

# Compile manuscript: fill placeholders from result JSONs
compile:
	$(PAPER_FORGE) compile

# Validate that all placeholders have corresponding result keys
check:
	$(PAPER_FORGE) check

# Render the compiled markdown to PDF via pandoc
pdf:
	$(PAPER_FORGE) render

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
	@echo "  make check     — validate placeholders against results"
	@echo "  make pdf       — render manuscript to PDF"
	@echo "  make pipeline  — units → compile → pdf"
	@echo "  make test      — run pytest"
	@echo "  make lint      — run ruff linter"
	@echo "  make format    — auto-format code with ruff"
	@echo "  make clean     — remove generated files"
