---
name: paper-analyze
description: React to a reviewer's analysis-shaped findings by proposing bounded changes to the data analysis (result units), inside Claude Code, without scope creep. Triages each finding fix/strengthen/expand, runs the data-analyst subagent only within the analysis charter, and gates every change. Use after /paper-review, or on a specific finding the user points at.
---

# paper-analyze

Turns reviewer analysis asks into **bounded, gate-verified changes to the data analysis** —
never unbounded new work. Runs on Claude Code primitives (the data-analyst is a subagent; the
gate is paper-forge). Companion to `/paper-review` (which produces the findings) and the
prose-editor (which handles wording). See `docs/review_loop_build_plan.md`.

## The scope rule (why this exists)
Reviewers always want more analysis; doing all of it balloons the paper and opens new attack
surface. So each analysis-shaped finding is triaged, and the boundary is **default-deny on
expansion**:

| Tier | What it is | Default action |
|---|---|---|
| **fix** | correct/reconcile a computation the paper already reports | **auto**: run the data-analyst |
| **strengthen** | add rigor (CI/test/sensitivity) to an existing claim, same data+features | **ask the human** first, then run |
| **deepen** | an unknown the **existing data** can answer, but no current RQ covers | **propose a `candidate` RQ** for a human to admit; only then build its units |
| **focus** | a claim/RQ is weak or under-supported | **propose** narrowing/dropping the RQ; human signs off |
| **expand** | needs **new data** / colonies / features / models | **propose only** — a rebuttal note; nothing runs |

The boundary is the **research-question registry** (`manuscript/research_questions.md`): every
result unit must serve a declared RQ (`paper-forge check-rqs` enforces it), so the breadth of
the analysis is bounded by the set of questions. Growing the analysis (`deepen`) or narrowing it
(`focus`) is a deliberate human amendment to that registry — that's what lets it change without
scope creep. `manuscript/review/charter.md` adds the data/feature/model bounds within each RQ.

## Steps
1. **Select findings.** Take the analysis-shaped findings (`kind` = stat/repro) from the latest
   `/paper-review` output, or the single finding the user named.
2. **Triage** each into fix/strengthen/expand, using the charter. State the tier and why.
3. **Route:**
   - **fix** → spawn `data-analyst` (worktree isolation) with the finding + the charter path.
   - **strengthen** → summarise the proposed analysis + cost, get the user's OK, then spawn.
   - **expand** → do not run; record a rebuttal-backlog entry (what it would take, whether it's
     worth it) for the response-to-reviewers, and tell the user.
4. **Gate.** Every candidate change from the analyst must pass `paper-forge check
   --strict-literals` + `compile` (+ `consistency` + `pytest` when present). Reject red candidates.
5. **Net-benefit check.** Keep a change only if the manuscript is stronger and no new weakness
   opened (a test that came back n.s., or a check that muddied a claim, goes to the human, not
   into the paper). Present before/after numbers and the diff for approval; do not auto-commit.

## Notes
- The analyst edits **result units only**, never prose — numbers change only via a gated unit.
- Data it cannot actually read (gated cluster paths) downgrades to a rebuttal note, not a result.
- Budget: ≤ 3 new/changed units per round.
