# `/scaffold` — Scaffold a New Paper Project

> Set up a new paper-forge project from scratch. Gathers requirements, initializes
> the project structure, and creates initial result unit stubs.

## Phase 1: Gather Requirements

1. Ask the user for:
   - **Research question** — what is the paper about?
   - **Data format** — what data files exist? (CSV, HDF5, database, etc.)
   - **Target journal** — formatting requirements (if known)
   - **Number of analyses** — rough count of statistical tests / result sections
   - **Co-authors** — names and affiliations for the YAML front matter

2. Confirm understanding before proceeding.

## Phase 2: Initialize Project

3. Navigate to the desired project directory.

4. Run the paper-forge init command:
   ```bash
   uv run paper-forge init <project-name>
   ```

5. Verify the generated structure:
   ```
   <project-name>/
   ├── project.yaml
   ├── Makefile
   ├── AGENT.md
   ├── .gitignore
   ├── manuscript/
   │   ├── manuscript_template.md
   │   ├── results/
   │   └── figures/
   ├── scripts/
   │   └── result_units/
   │       ├── __init__.py
   │       └── 01_example.py
   └── tests/
       └── test_example.py
   ```

## Phase 3: Configure project.yaml

6. Update `project.yaml` with:
   - Project name and title
   - Author information
   - Plan the result unit prefix map based on the analyses identified in Phase 1
   - If the project has a bibliography, add a `citations:` block (path, enforcement, coverage threshold)

   Example:
   ```yaml
   result_units:
     prefix_map:
       "01_demographics": "demo"
       "02_primary_outcome": "pri"
       "03_secondary_outcome": "sec"
   citations:
     bibliography: "references.bib"
     enforce: false
     flag_prose_attributions: true
     require_verified: false   # true = citing an unverified .bib fails the gate
   ```

## Phase 4: Create Result Unit Stubs

7. For each planned analysis, create a stub script in `scripts/result_units/`:
   ```python
   #!/usr/bin/env python3
   """NN_name — Brief description of this analysis."""
   from pathlib import Path
   from paper_forge.result_unit import save_results

   RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"

   def main() -> None:
       # TODO: Load data
       # TODO: Run analysis
       # TODO: Build results dict
       results = {}
       save_results("NN_name", results, output_dir=RESULTS_DIR)

   if __name__ == "__main__":
       main()
   ```

8. Update the prefix map in `project.yaml` for each new unit.

## Phase 5: Draft Template Structure

9. Edit `manuscript/manuscript_template.md`:
   - Set up the YAML front matter (title, authors, abstract)
   - Create section headers: Introduction, Methods, Results, Discussion
   - Add placeholder comments where results will go:
     ```markdown
     ## Primary Outcome
     <!-- TODO: Add placeholders from 02_primary_outcome (prefix: pri) -->
     ```

10. Add known static text (methods description, introduction background).

## Phase 6: Validate

11. Run validation:
    ```bash
    make check
    ```

12. Fix any issues reported by the checker.

13. Initialize git repository:
    ```bash
    git init
    git add .
    git commit -m "Initial paper-forge scaffold"
    ```

14. If the project includes a bibliography, review its entries. Once satisfied,
    record the sign-off and commit the lock file:
    ```bash
    paper-forge verify-bib references.bib --note "entries reviewed at scaffold"
    git add bibliography.lock
    git commit -m "Record initial bibliography verification"
    ```
    Without this step the bibliography is in *draft* state — citing it is reported
    as `unverified-entry` (a warning by default; fatal if `require_verified: true`
    is set later). Commit `bibliography.lock` alongside the .bib so any subsequent
    change is detected as `modified-bibliography`.

## Completion Checklist

- [ ] `project.yaml` configured with correct prefix map
- [ ] Result unit stubs created for all planned analyses
- [ ] Template has section structure with placeholder comments
- [ ] Bibliography configured in `project.yaml` and `paper-forge tokens` run to produce the token table (if using a .bib)
- [ ] `bibliography.lock` committed after reviewing bibliography entries (`paper-forge verify-bib`; if using a .bib)
- [ ] `make check` passes (or only reports expected TODOs)
- [ ] Git repository initialized
