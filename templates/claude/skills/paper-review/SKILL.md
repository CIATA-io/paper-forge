---
name: paper-review
description: Run a grounded peer review of the paper-forge manuscript inside Claude Code (no external LLM). Compiles the manuscript, spawns the manuscript-reviewer subagent against the rubric, verifies its numeric claims against the result units, and reports ranked findings. Use when the user asks to review the paper, get referee feedback, or run the review loop.
---

# paper-review

A read-only manuscript review that runs entirely on Claude Code primitives — the reviewer is
a **subagent**, the gate is **paper-forge** (deterministic Python). No API keys, no external
service. This is milestone M0 of the review loop; M2+ add the editor and the keep/discard loop
(see `docs/review_loop_build_plan.md`).

## Steps

1. **Gate first.** Run `paper-forge gate` (or, until it exists, `paper-forge check
   --strict-literals` + `paper-forge compile`). If the manuscript doesn't compile cleanly or has
   hardcoded literals, stop and report that — there's nothing stable to review.

2. **Gather context.** Identify the compiled manuscript (`project.yaml` → `manuscript.output_md`),
   the rubric (`manuscript/review/rubric.md`), and the result JSONs (`manuscript/results/*.json`).

3. **Spawn the reviewer.** Launch the `manuscript-reviewer` subagent (Agent tool). In its prompt,
   give the paths from step 2 and instruct it to score against the rubric and return the
   structured JSON. It is read-only. If `manuscript-reviewer` isn't a registered agent type,
   spawn `general-purpose` and paste this repo's `.claude/agents/manuscript-reviewer.md` body as
   the role, plus the rubric path.

4. **Verify numeric claims.** For each finding with `numeric_claim: true`, run `paper-forge
   consistency` (once implemented) or directly check the named `provenance_key` against
   `manuscript/results/<unit>.json`. Drop or downgrade any finding the JSON contradicts — the
   reviewer must not win on a hallucinated discrepancy.

5. **Report.** Present the findings ranked most-severe first (blocking → major → minor), each
   with its section, the grounded evidence, and the suggested fix. Lead with the overall score,
   subscores, and the accept/minor/major/reject recommendation. Do **not** apply any edits —
   this milestone is review-only.

## Notes
- Calibrate the reviewer against any existing manual review (e.g. `docs/v19_review/peer_review.md`):
  it should independently surface the same major issues.
- The reviewer edits nothing; the editor subagent + keep/discard loop are later milestones.
