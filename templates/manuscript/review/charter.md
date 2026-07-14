# Analysis charter — <YOUR PAPER TITLE>

The scope boundary for the paper-forge `data-analyst` agent (see the `/paper-analyze` skill). The
analyst may operate **only within this charter**. Anything outside it requires a human to amend
this file first — and that amendment is the deliberate act that lets the paper's analysis grow.
Reviewers routinely ask for more analysis; the charter is what keeps "more" from happening by
default.

> **This is a template.** Copy it to `manuscript/review/charter.md` and fill in your data
> sources, analysis window, feature sets, and models. The In-scope / Out-of-scope / Budget
> structure is what bounds the agent — keep it.

## In scope (the analyst may fix or strengthen these)

**Data (already in the repo, or on a declared, readable path):**
- `<path/to/results.json>` — <what it holds>.
- `<path/to/other-input.csv>` — <what it holds>.

**Analysis window / sample:** <e.g. date range; N units; whether it is fixed>.

**Feature sets:** <the feature families in play>. No new feature families without a charter amendment.

**Models / protocol:** <readout, cross-validation, hyperparameters, baseline / null model>.
No new model classes without a charter amendment.

**Permitted operations:**
- **fix** — reconcile/correct a computation the paper already reports (a stored value that
  disagrees with its own recompute; a subset mismatch; an underspecified statistic).
- **strengthen** — add rigor to an *existing* claim over the *same* data + features: a bootstrap
  CI on a reported number, a significance test for a comparison already made, a sensitivity check
  on the reported results. (By default, propose first and run only once a human approves.)

## Out of scope (charter amendment required — the analyst may only *propose*, in a rebuttal note)

- More samples / subjects / sites / seasons.
- New feature families, new model classes (e.g. nonlinear readouts), or new data modalities.
- New data acquisition, or reprocessing that needs access you do not currently have.
- Any analysis whose result would require **re-framing a central claim** rather than supporting it.

## Data-access reality

Anything that needs data you cannot actually read (gated cluster paths, unreleased raw data)
**cannot be run** and must downgrade to a rebuttal note, not a pretend result. Only analyses
reproducible from the readable, in-repo data run without a data-access change.

## Budget (per review round)

- ≤ 3 new/changed result units.
- Every changed number must flow through a result unit and pass the gate —
  `paper-forge check --strict-literals` → `compile` → `check-rqs` (plus `pytest` when the project
  has tests). No hand-entered numbers.
- **Net-benefit rule:** keep a change only if re-review shows the manuscript got stronger and no
  new weakness opened. A test that comes back non-significant, or a check that muddies a claim, is
  surfaced for a human decision — never auto-included.
