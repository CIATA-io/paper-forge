# `/draft_template` — Draft Manuscript Template from Results

> Generate a complete manuscript template by reading existing result JSONs and
> wiring up placeholders. This workflow is ideal when result units already exist
> and you need to build or rebuild the manuscript template.

## Phase 1: Inventory Results

1. List all available result JSONs:
   ```bash
   ls -la manuscript/results/*.json
   ```

2. For each JSON, extract the available keys:
   ```bash
   for f in manuscript/results/*.json; do
     echo "=== $(basename $f) ==="
     uv run python -c "
   import json
   with open('$f') as fh:
       data = json.load(fh)
       results = data.get('results', data)
       for k, v in sorted(results.items()):
           print(f'  {k}: {type(v).__name__} = {repr(v)[:60]}')
   "
   done
   ```

3. Read the prefix map from `project.yaml`:
   ```bash
   cat project.yaml
   ```

4. Build a mapping table:

   | JSON file | Prefix | Available keys |
   |-----------|--------|----------------|
   | 01_population.json | pop | n_total, n_deprived, ... |
   | 02_temporal.json | temp | n_morning, temporal_p, ... |

## Phase 2: Check for Research Questions

5. If `research_questions.yaml` exists, read it for structure guidance:
   ```bash
   cat research_questions.yaml 2>/dev/null || echo "No research_questions.yaml found"
   ```

   Expected format:
   ```yaml
   questions:
     - id: RQ1
       text: "Does sleep deprivation affect dance accuracy?"
       result_units: ["01_population"]
     - id: RQ2
       text: "Does the effect vary with time of day?"
       result_units: ["02_temporal"]
   ```

## Phase 3: Generate Template

6. Create `manuscript/manuscript_template.md` with this structure:

### YAML Front Matter
```markdown
---
title: "Paper Title"
author:
  - name: "Author"
    affiliation: "Institution"
abstract: |
  Summary with key numbers: {{prefix.key:formatter}}
---
```

### Section Guidelines

**Introduction:**
- Static text — no placeholders needed
- End with clear hypotheses

**Methods:**
- Mostly static text
- Use placeholders for sample sizes: `{{pop.n_total:int}}`
- Describe statistical methods

**Results:**
- Heavy use of placeholders
- Pattern for each test:
  ```markdown
  Group A (Mdn = {{prefix.median_a:fmt2}}) differed from
  Group B (Mdn = {{prefix.median_b:fmt2}};
  U = {{prefix.u_stat:fmt1}}, {{prefix.p_value:p}},
  r = {{prefix.effect_size:r}}).
  {{prefix.interp}}
  ```

**Discussion:**
- Use interpretation placeholders to echo key findings
- Reference effect sizes: `{{prefix.effect_size:r}}`

## Phase 4: Wire Up Interpretation Rules

7. For each p-value in a result unit, ensure there is a corresponding
   interpretation key that generates text based on the statistical result.

8. Common interpretation patterns:
   ```python
   # In the result unit:
   if p < 0.001:
       interp = "The effect was highly significant..."
   elif p < 0.05:
       interp = "The effect was significant..."
   else:
       interp = "No significant effect was observed..."
   ```

9. For each interpretation placeholder in the template, verify the result
   unit generates the text dynamically (not hardcoded).

## Phase 5: Compile and Validate

10. Run validation:
    ```bash
    make check
    ```

11. Fix any issues:
    - **Missing key**: Add the key to the result unit, or remove the placeholder
    - **Orphaned key**: Result exists but no placeholder uses it (warning only)
    - **Wrong prefix**: Check `project.yaml` prefix map

12. Compile:
    ```bash
    make compile
    ```

13. Review the compiled output:
    ```bash
    cat manuscript/manuscript.md
    ```

14. Check for:
    - [ ] All `{{...}}` placeholders replaced
    - [ ] Numbers formatted correctly
    - [ ] Interpretation text reads naturally
    - [ ] No duplicate or contradictory statements
    - [ ] Logical flow between sections

## Phase 6: Render and Review

15. Generate PDF:
    ```bash
    make pdf
    ```

16. Review the PDF for formatting issues.

## Completion Checklist

- [ ] All result JSON keys mapped to template placeholders
- [ ] `make check` passes with no errors
- [ ] `make compile` produces clean manuscript.md
- [ ] Interpretation text is dynamically generated
- [ ] Manuscript reads as coherent prose (not just numbers)
