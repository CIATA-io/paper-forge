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

   Example:
   ```yaml
   result_units:
     prefix_map:
       "01_demographics": "demo"
       "02_primary_outcome": "pri"
       "03_secondary_outcome": "sec"
   ```

## Phase 4: Create Result Unit Stubs

7. For each planned analysis, create a stub script in `scripts/result_units/`:
   ```python
   #!/usr/bin/env python3
   """NN_name — Brief description of this analysis."""
   from pathlib import Path
   from paper_forge.result_unit import save_results
   from paper_forge.provenance import get_git_provenance

   RESULTS_DIR = Path(__file__).resolve().parents[2] / "manuscript" / "results"

   def main() -> None:
       # TODO: Load data
       # TODO: Run analysis
       # TODO: Build results dict
       results = {}
       provenance = get_git_provenance(Path(__file__))
       save_results(results=results, output_dir=RESULTS_DIR,
                    unit_name="NN_name", provenance=provenance)

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

## Completion Checklist

- [ ] `project.yaml` configured with correct prefix map
- [ ] Result unit stubs created for all planned analyses
- [ ] Template has section structure with placeholder comments
- [ ] `make check` passes (or only reports expected TODOs)
- [ ] Git repository initialized
