# Research questions

The scope boundary for the analysis. **Every result unit must serve a research question
here** (declared via `rq=` in `save_results`), and every non-dropped question must be backed
by at least one unit — `paper-forge check-rqs` enforces both. The set of questions is therefore
the natural limit on how broad the analysis can get.

Growing or narrowing the analysis is a deliberate edit to *this file*:
- **deepen** — admit a new question the existing data can answer: add a block with
  `status: candidate`, then (after you're happy) `status: open`; its units may then be built.
- **focus** — retire a weak question: set `status: dropped` and remove its units.
- Questions needing *new data* you don't have are **not** added here — they belong in the
  response-to-reviewers as future work.

Statuses: `open` (being pursued) · `answered` (reported in the manuscript) · `candidate`
(proposed, not yet admitted — may have no units yet) · `dropped` (retired).

Descriptive/setup units that characterise the data rather than answer a question declare
`rq="methods"` and don't need a block here.

---

## RQ1 — <short title>
- **question:** <the precise question, phrased so a result unit can answer it>
- **status:** open
- **units:** 01_example

## RQ2 — <short title>
- **question:** <...>
- **status:** candidate
- **units:**
