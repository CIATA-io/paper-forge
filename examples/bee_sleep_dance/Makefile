# Bee Sleep Dance example — Makefile
# ============================================================

PYTHON ?= uv run python
PAPER_FORGE ?= uv run paper-forge

.PHONY: all compile check pdf units clean help

all: compile pdf

units:
	@$(PYTHON) scripts/result_units/01_population.py
	@$(PYTHON) scripts/result_units/02_temporal.py

compile:
	$(PAPER_FORGE) compile

check:
	$(PAPER_FORGE) check

pdf:
	$(PAPER_FORGE) render

pipeline: units compile pdf

clean:
	rm -f manuscript/manuscript.md
	rm -f manuscript/manuscript.pdf
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

help:
	@echo "Targets: all units compile check pdf pipeline clean"
