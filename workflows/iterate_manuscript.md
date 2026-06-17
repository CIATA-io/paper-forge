# `/iterate` — Iterate on Manuscript Based on Feedback

> Refine the manuscript based on reviewer, co-author, or editor feedback.
> Identifies which result units or template sections need changes, makes
> targeted edits, recompiles, and verifies.

## Phase 1: Read and Categorize Feedback

1. Read the feedback document or message from the user.

2. Categorize each piece of feedback:

   | Category | Example | Action needed |
   |----------|---------|---------------|
   | **Statistics** | "Report confidence intervals" | Modify result unit |
   | **Prose** | "Rephrase the discussion" | Edit template |
   | **Formatting** | "Use 3 decimal places for r" | Change formatter |
   | **Analysis** | "Add a subgroup analysis" | New result unit |
   | **Structure** | "Move methods before results" | Reorganize template |
   | **Data** | "Exclude outliers" | Modify result unit |

3. Create a checklist of changes:
   ```markdown
   - [ ] Add 95% CI to primary outcome (result unit: 02_primary)
   - [ ] Rephrase discussion paragraph 2 (template)
   - [ ] Add subgroup analysis (new unit: 04_subgroup)
   - [ ] Use APA 7th edition p-value format (template formatters)
   ```

## Phase 2: Identify Impact

4. For each change, determine what files are affected:

   ```bash
   # Find all placeholders using a prefix
   grep -n 'pri\.' manuscript/manuscript_template.md

   # Find the result unit that produces a prefix
   grep -A5 'prefix_map' project.yaml
   ```

5. Check for cascading effects:
   - If changing sample size (e.g., excluding outliers), ALL statistics
     from that dataset will change
   - If adding a new result unit, need to update `project.yaml` AND template

## Phase 3: Make Changes

### For Result Unit Changes

6. Edit the result unit script:
   ```bash
   # e.g., add confidence intervals
   $EDITOR scripts/result_units/02_primary.py
   ```

7. Add new keys to the results dict:
   ```python
   results["ci_lower"] = float(ci[0])
   results["ci_upper"] = float(ci[1])
   ```

8. Re-run the unit:
   ```bash
   uv run python scripts/result_units/02_primary.py
   ```

9. Verify the new JSON output:
   ```bash
   cat manuscript/results/02_primary.json | python -m json.tool
   ```

### For Template Changes

10. Edit the manuscript template:
    ```bash
    $EDITOR manuscript/manuscript_template.md
    ```

11. Add placeholders for any new result keys:
    ```markdown
    (95% CI [{{pri.ci_lower:fmt2}}, {{pri.ci_upper:fmt2}}])
    ```

### For New Result Units

12. Follow the `/write_unit` workflow to create the new unit.

13. Update `project.yaml` with the new prefix mapping.

## Phase 4: Recompile and Verify

14. Run the full pipeline:
    ```bash
    make pipeline  # units + compile + pdf
    ```

15. If only template changed (no new data):
    ```bash
    make all  # compile + pdf
    ```

16. Run validation:
    ```bash
    make check
    ```

## Phase 5: Diff Against Previous Version

17. Compare the compiled manuscript against the previous version:
    ```bash
    git diff manuscript/manuscript_template.md
    ```

18. If result JSONs are tracked:
    ```bash
    git diff manuscript/results/
    ```

19. Review changes in the compiled output:
    ```bash
    # Compile first, then diff
    make compile
    git diff manuscript/manuscript.md
    ```

20. Verify the changes address all feedback items:
    - [ ] Each feedback item has been addressed
    - [ ] No unintended changes to other sections
    - [ ] Numbers are still consistent across sections
    - [ ] New statistics are correctly formatted

## Phase 6: Finalize

21. Run tests:
    ```bash
    make test
    ```

22. Generate final PDF:
    ```bash
    make pdf
    ```

23. Commit changes:
    ```bash
    git add -A
    git commit -m "Address reviewer feedback: [summary of changes]"
    ```

24. Update the feedback checklist — mark all items as done.

## Tips for Common Reviewer Requests

### "Report effect sizes"
Add to result unit: compute Cohen's d, r, η², etc.
Add to template: `(d = {{prefix.cohens_d:fmt2}})`

### "Add confidence intervals"
Add to result unit: compute via bootstrap or analytical formula.
Add to template: `(95% CI [{{prefix.ci_lo:fmt2}}, {{prefix.ci_hi:fmt2}}])`

### "Use Bonferroni correction"
Modify result unit: adjust p-values.
The template placeholders don't change — they just show the corrected values.

### "Report exact p-values"
This is a formatter change. Use `:p` which already handles this per APA guidelines.

### "Add a table"
Tables can use placeholders too:
```markdown
| Group | M | SD | n |
|-------|---|----|----|
| Treatment | {{pri.mean_tx:fmt2}} | {{pri.sd_tx:fmt2}} | {{pri.n_tx:int}} |
| Control | {{pri.mean_ctrl:fmt2}} | {{pri.sd_ctrl:fmt2}} | {{pri.n_ctrl:int}} |
```
