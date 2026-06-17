#!/usr/bin/env bash
# run_all_units.sh — Execute all result units in order.
#
# Usage:
#   ./scripts/run_all_units.sh
#
# This script runs each result unit script in numerical order.
# Each unit produces a JSON file in manuscript/results/.
# After all units complete, you can run `make compile` to build the manuscript.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UNITS_DIR="$SCRIPT_DIR/result_units"

# Read python command from project.yaml, default to "uv run python"
PYTHON="${PAPER_FORGE_PYTHON:-uv run python}"

echo "═══════════════════════════════════════════════════"
echo "  paper-forge: Running all result units"
echo "═══════════════════════════════════════════════════"
echo ""

# Find and run all result unit scripts (NNN_*.py) in order
UNIT_COUNT=0
FAIL_COUNT=0

for unit in "$UNITS_DIR"/[0-9]*_*.py; do
    [ -f "$unit" ] || continue
    UNIT_NAME="$(basename "$unit" .py)"
    UNIT_COUNT=$((UNIT_COUNT + 1))

    echo "▶ Running: $UNIT_NAME"
    if $PYTHON "$unit"; then
        echo "  ✓ Done"
    else
        echo "  ✗ FAILED (exit code $?)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    echo ""
done

echo "═══════════════════════════════════════════════════"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  ✗ $FAIL_COUNT of $UNIT_COUNT units failed"
    exit 1
else
    echo "  ✓ All $UNIT_COUNT units completed successfully"
fi
echo "═══════════════════════════════════════════════════"
