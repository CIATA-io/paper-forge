# `/write_unit` — Write a Result Unit

> Create a result unit script that loads data, runs a statistical analysis,
> and saves structured JSON output for the manuscript compiler.

## Phase 1: Understand the Analysis

1. Ask the user for:
   - **What analysis** — what statistical test or computation?
   - **Input data** — where is the data? What format?
   - **Expected outputs** — what numbers should appear in the manuscript?
   - **Unit name** — e.g., `03_survival_analysis`
   - **Prefix** — short prefix for placeholders, e.g., `surv`

2. Review existing result units for style consistency:
   ```bash
   ls scripts/result_units/
   ```

3. Check the manuscript template for any existing placeholders that reference this prefix.

## Phase 2: Create the Script

4. Determine the next available number:
   ```bash
   ls scripts/result_units/[0-9]*_*.py | tail -1
   ```

5. Create `scripts/result_units/NN_name.py` with this structure:
   ```python
   #!/usr/bin/env python3
   """NN_name — Description of this analysis.

   Input: path/to/data.csv
   Output: manuscript/results/NN_name.json
   Prefix: prefix
   """
   from pathlib import Path
   import numpy as np
   from scipy import stats
   from paper_forge.result_unit import save_results
   from paper_forge.provenance import get_git_provenance

   RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"
   DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "input.csv"

   def main() -> None:
       # 1. Load data
       # 2. Clean / filter
       # 3. Run statistical tests
       # 4. Generate interpretation text from p-values
       # 5. Build results dict
       # 6. Save

       results = {
           # Sample sizes (always include these)
           "n_total": ...,

           # Raw statistics
           "test_stat": ...,
           "p_value": ...,
           "effect_size": ...,

           # Descriptive stats
           "mean_group1": ...,
           "sd_group1": ...,

           # Interpretation text
           "main_interp": "...",
       }

       provenance = get_git_provenance(Path(__file__))
       save_results(
           results=results,
           output_dir=RESULTS_DIR,
           unit_name="NN_name",
           provenance=provenance,
       )

   if __name__ == "__main__":
       main()
   ```

### Result Dict Design Rules

- **Keys are snake_case** — they become placeholder names
- **All numbers are raw** — formatting happens in the compiler
- **Include interpretation text** — generate from p-values, not hardcode
- **Include sample sizes** — always report n for every comparison
- **No nested dicts** — keep it flat for simple placeholder syntax

## Phase 3: Update Configuration

6. Add the new unit to `project.yaml`:
   ```yaml
   result_units:
     prefix_map:
       "NN_name": "prefix"
   ```

## Phase 4: Run and Verify

7. Run the result unit:
   ```bash
   uv run python scripts/result_units/NN_name.py
   ```

8. Inspect the output JSON:
   ```bash
   cat manuscript/results/NN_name.json | python -m json.tool
   ```

9. Verify:
   - [ ] All expected keys are present
   - [ ] Numbers are plausible
   - [ ] P-values are in [0, 1]
   - [ ] Effect sizes are in expected range
   - [ ] Interpretation text matches the p-value
   - [ ] Provenance metadata is included

## Phase 5: Add Placeholders to Template

10. Edit `manuscript/manuscript_template.md` to add placeholders:
    ```markdown
    The survival rate was {{surv.rate:pct}} (n = {{surv.n_total:int}}).
    A log-rank test revealed a {{surv.significance}} difference between
    groups (χ² = {{surv.chi2:fmt2}}, {{surv.p_value:p}}).
    {{surv.main_interp}}
    ```

11. Follow these placeholder guidelines:
    - Use `:int` for counts and sample sizes
    - Use `:fmt2` for means, SDs, and descriptive stats
    - Use `:r` for correlations and effect sizes
    - Use `:p` for p-values (auto-formats to APA style)
    - Use `:pct` for percentages
    - No formatter needed for text/interpretation values

## Phase 6: Validate

12. Run the checker:
    ```bash
    make check
    ```

13. Fix any reported issues (missing keys, orphaned placeholders).

14. Compile and review:
    ```bash
    make compile
    cat manuscript/manuscript.md
    ```

## Phase 7: Test

15. Add a test in `tests/test_NN_name.py`:
    ```python
    def test_required_keys(example_results):
        for key in ["n_total", "p_value", "main_interp"]:
            assert key in example_results["results"]
    ```

16. Run tests:
    ```bash
    make test
    ```
