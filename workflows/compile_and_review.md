# `/compile` — Compile and Review Manuscript

> Run the full pipeline: execute result units, compile the manuscript,
> validate, render to PDF, and review for consistency.

## Phase 1: Run Result Units

1. Run all result unit scripts:
   ```bash
   make units
   ```

2. If any unit fails, fix the error and re-run:
   ```bash
   uv run python scripts/result_units/NN_name.py
   ```

3. Verify all expected JSON files exist:
   ```bash
   ls -la manuscript/results/*.json
   ```

4. Spot-check a result file:
   ```bash
   cat manuscript/results/01_*.json | python -m json.tool
   ```

## Phase 2: Compile Manuscript

5. Run the compiler:
   ```bash
   make compile
   ```

6. The compiler will:
   - Read `project.yaml` for configuration
   - Load all JSON files from `manuscript/results/`
   - Map keys via the prefix map
   - Fill `{{prefix.key:formatter}}` placeholders in the template
   - Write the compiled output to `manuscript/manuscript.md`

## Phase 3: Check for Issues

7. Run the placeholder validator:
   ```bash
   make check
   ```

8. Common issues and fixes:

   | Issue | Cause | Fix |
   |-------|-------|-----|
   | `Missing key: pop.n_total` | Key not in JSON | Add to result unit |
   | `Unknown prefix: xyz` | Not in prefix map | Update `project.yaml` |
   | `Unfilled placeholder` | JSON missing value | Run result unit |
   | `Unknown formatter: foo` | Typo in template | Fix formatter name |

9. Verify no raw `{{...}}` placeholders remain in the compiled output:
   ```bash
   grep -n '{{' manuscript/manuscript.md
   ```
   This should return no results.

## Phase 4: Render PDF

10. Render to PDF:
    ```bash
    make pdf
    ```

11. If pandoc fails, check:
    - Is pandoc installed? (`pandoc --version`)
    - Is xelatex installed? (`xelatex --version`)
    - Are there LaTeX errors in the markdown?

## Phase 5: Review for Prose–Data Consistency

12. Open `manuscript/manuscript.md` and review:

### Numbers Check
- [ ] All reported n's are consistent across sections
- [ ] Abstract numbers match Results section numbers
- [ ] Methods sample sizes match Results sample sizes
- [ ] Effect sizes and p-values appear in pairs

### Prose Check
- [ ] Interpretation text matches the reported statistics
- [ ] "significant" claims have p < .05
- [ ] "non-significant" claims have p ≥ .05
- [ ] Direction words ("higher", "lower") match the data
- [ ] Effect magnitude descriptors match effect size values

### Format Check
- [ ] P-values formatted correctly (p = .023, p < .001)
- [ ] Numbers have appropriate decimal places
- [ ] Percentages have % symbol
- [ ] No orphaned formatting artifacts

13. If issues found, trace back to the source:
    - **Wrong number** → fix the result unit script
    - **Wrong interpretation** → fix the interpretation logic in the result unit
    - **Wrong formatting** → fix the formatter in the template placeholder
    - **Wrong prose** → fix the static text in the template

14. After fixes, recompile:
    ```bash
    make compile
    make pdf
    ```

## Quick Pipeline (No Issues Expected)

For a routine recompile when you trust the result units:
```bash
make all  # compile + pdf in one step
```

For the full pipeline from scratch:
```bash
make pipeline  # units + compile + pdf
```
