# paper-forge: review & roadmap (review-loop integration)

*Author: review requested by Tim Landgraf, 2026-07. Context: the bb_reservoir_computing
manuscript exposed both a strength (numbers-from-code) and a gap (nothing enforces it),
and raised the question of integrating an autonomous LLM-reviewer loop (à la Karpathy's
autoresearch) into paper-forge.*

---

## 1. Review of the current system

paper-forge is well-architected for a young project: the 4-layer split (result units →
template → compiled md → PDF), the "interpretation lives in the unit" decision, git
provenance in every JSON, LaTeX/Unicode-aware formatters, a real test suite, an example
project, and shipped agent workflows (`scaffold`, `write_unit`, `draft_template`,
`compile`, `iterate`). The core value proposition — *no number is ever typed by hand* — is
the right invariant.

**The central gap: the invariant is documented, not enforced.**
`validators.check_placeholders` verifies that every `{{...}}` *resolves*; `check_figures`
verifies figures exist. Nothing scans for a **hardcoded numeric literal typed into the
prose** (`37%`, `n = 42`, `MC = 2.67`). So a human — or an LLM revising the draft — can
paste or hallucinate a number and paper-forge stays silent. This is exactly what bit the
reservoir paper: revisions went into a hand-maintained `main.md` full of literal numbers,
the template drifted, and `compile` silently produced a regressed manuscript.

Everything below is prioritized around closing that gap, because it is also the
precondition for a *safe* autonomous review loop.

## 2. Proposed improvements (prioritized)

**P0 — Numeric-literal guard (`paper-forge check --no-literals`).**
Scan the template for digit-bearing tokens *outside* `{{...}}`, fenced code, YAML
front-matter, figure paths, and an allowlist (citation years, section numbers, and lines
explicitly marked `<!-- pf-allow-literal: reason -->`). Fail the check if any remain. This
turns the "numbers → prose, never the reverse" philosophy into an enforced guarantee. Ship
it in `check` and as a pre-commit hook. *~1 module + tests.*

**P0 — Strict compile.** `compile()` currently leaves unresolved `{{...}}` in the output
and only warns (compiler.py:352–361). Add `--strict` (fail on any unresolved placeholder)
and make it the pipeline default, so a broken slot can't reach a PDF.

**P1 — Staleness detection (`check --stale`).** Flag a result JSON that is older than (a)
its result-unit script or (b) its declared input data. This generalizes the main.md↔template
drift problem: it catches "the number in the paper was computed by code that has since
changed." Provenance already records a git commit — compare it to the unit's current hash.

**P1 — Numbers audit (`paper-forge audit`).** Provenance is captured but never surfaced.
Emit a table mapping every rendered number → key → unit → commit, and optionally a
manuscript appendix. Reviewers and co-authors get a from-any-number-to-the-code trail;
authors get a diff when results change.

**P1 — Single source of truth.** The reservoir repo carries *both* `main.md` and
`manuscript_template.md` — the anti-pattern paper-forge exists to prevent. Recommend
(and document) that the template is the *only* prose source and the compiled `manuscript.md`
is the artifact; never hand-edit the compiled file. A `check` that diffs a committed
`manuscript.md` against a fresh compile (and fails on drift) enforces it in CI.

**P2 — Reference/citation validator.** Numbers include reference years; a `:cite`
mechanism (or a `.bib` + CrossRef/DOI check) would verify citations resolve to real papers.
This would have caught the fabricated reference [6] (real title, invented authors/venue/year)
in the reservoir manuscript automatically.

**P2 — Harden `derived` eval.** `_resolve_derived` uses `eval` with a builtin allowlist
(compiler.py:252). Move to `simpleeval` or an AST-restricted evaluator.

**P2 — Formatter robustness + property tests.** Type-mismatch errors (formatter on a
string/None) should be caught in `check` with a clear message; add property tests for the
formatters.

## 3. The synergy: why paper-forge makes an autonomous review loop *safe*

Karpathy's autoresearch loop is: *agent edits `train.py` → 5-min eval → keep iff `val_bpb`
improved → repeat*. The obvious manuscript analogue is: *agent edits the paper → LLM
reviewer scores it → keep iff the score improved → repeat*. The problem everyone hits is
that **an LLM editing a manuscript hallucinates and drifts numbers.**

paper-forge dissolves that problem. If the editor agent may only touch the **template**
(prose + placeholders) and the **result units** (code), and every candidate must pass the
P0 guards before it is even scored, then:

- numbers can change **only** by editing a unit, which **recomputes them from data** — the
  agent physically cannot invent a result;
- prose edits that smuggle in a literal number are rejected by the numeric-literal guard;
- broken references are caught by the citation validator.

So paper-forge's numbers-from-code invariant is precisely the **safety gate** that makes an
autonomous paper-revision loop trustworthy. This is the novel contribution and worth a
methods note in its own right ("self-revising reproducible manuscripts").

## 4. Proposed `paper-forge review-loop`

```
loop(manuscript, rubric, budget):
  1. COMPILE      template + units → manuscript.md         (must pass check --strict --no-literals --stale)
  2. REVIEW       LLM reviewer panel scores manuscript.md against a journal rubric
                  → structured issues (severity, line, provenance ref) + scalar score
  3. CONSISTENCY  auto-verify every "wrong number" claim against the result JSON
                  (reviewer cannot hallucinate a discrepancy)
  4. EDIT         editor agent proposes MINIMAL diffs to template/units for the top issues
  5. GATE         recompile + all P0/P1 checks + unit tests; reject candidate if any fail
  6. SCORE        re-review; keep iff score improved (autoresearch keep/discard), else discard
  7. LOG          append round to a review log (branch/PR per accepted change)
  repeat until score plateaus or budget exhausted
```

Design choices:
- **Reviewer = eval metric.** Structured output: rubric sub-scores (novelty, rigor, clarity,
  reproducibility) → one scalar to optimize. Multiple personas (journal referee, stats
  referee, skeptic) — exactly what Daniele produced by hand in `docs/v19_review/`. Those
  become the seed rubric/persona prompts.
- **Reuse `auto_deep_research`.** It already has GDPR-compliant LLM plumbing (AKI.io), a
  fact-checker, and coverage/quality gates — the reviewer, consistency-checker, and gate map
  onto that infrastructure.
- **Human-in-the-loop by default.** Accepted diffs land on a review branch as commits/PRs
  (like autoresearch's overnight experiment log); a human merges. A `--auto` mode can run
  overnight and present the log in the morning.
- **The score is only ever a *proposal signal*.** Final scientific judgment stays with the
  authors; the loop's job is to surface issues and draft defensible revisions, never to
  auto-publish.

## 5. Sequencing (recommended)

1. **P0 numeric-literal guard + strict compile** — small, high-value, and the prerequisite
   for both a clean template rewrite and a safe loop.
2. **Rewrite the reservoir `manuscript_template.md` from `main.md`**, using the guard to
   prove zero literals remain (numbers that main.md introduced but no unit emits yet — the
   leakage replication 29/38 & p, waggle r=+0.42/−0.25, ICC, lag-1 r, weather correlations —
   get added to units first). Then `main.md` becomes a generated artifact.
3. **P1 audit + staleness + single-source CI.**
4. **`review-loop` MVP** reusing `auto_deep_research`, seeded with Daniele's rubric, human-
   in-the-loop, on the now-clean reservoir manuscript as the first real test case.
