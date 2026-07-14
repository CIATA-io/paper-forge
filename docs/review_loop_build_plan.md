# Build plan: `paper-forge` review loop — **Claude Code native**

*Concrete plan for the autonomous review loop sketched in
[review_and_roadmap.md](review_and_roadmap.md) §3–5. Constraint (Tim): it must run **inside
Claude Code** — no external LLM API, no keys, no `auto_deep_research`/SDK calls. The
"intelligence" is Claude Code **subagents**; paper-forge stays a deterministic Python gate.*

## The split that makes this work

| Layer | Who | Runs as |
|---|---|---|
| **Reviewer** — critique manuscript vs rubric → findings + score | Claude Code subagent | `Agent` / `Task` tool (or a `.claude/agents/*.md` type) |
| **Editor** — propose minimal diffs to template/units for top findings | Claude Code subagent | `Agent` tool, `isolation: worktree` |
| **Gate** — recompile + `check --strict-literals` + consistency + tests | **paper-forge (Python)** | `Bash` — deterministic, no LLM |
| **Orchestration** — compile → review → edit → gate → keep/discard | Claude Code **skill** (or a `Workflow` when the user opts in) | the running agent |

Nothing here calls an LLM API. The reviewer/editor are subagents in the same Claude Code
session (already authenticated, local). paper-forge gains only deterministic CLI pieces.

## Why it's safe (unchanged, and now fully local)

The editor subagent may touch **only** the template (prose + placeholders) and **result
units** (code). Every candidate must pass the paper-forge gate before it's scored:
`compile → check --strict-literals → consistency-check → pytest`. So numbers can change only
by editing a unit that recomputes from data; a literal typed into prose is rejected; a
"wrong number" claim from the reviewer is auto-verified against the result JSON. The LLM
revises argument and analysis; it cannot invent results — and none of that safety depends on
an external service.

## New deterministic paper-forge pieces (Python, no LLM)

- **`paper-forge review-context`** — bundle what a reviewer subagent needs into one file:
  the compiled manuscript, the rubric, and the number→key→unit→commit provenance map (so the
  reviewer can cite where each number came from and can't hallucinate a discrepancy).
- **`paper-forge consistency`** — verify every number rendered in the manuscript still equals
  its result-unit value (re-render placeholders and diff). Exit non-zero on any mismatch.
  This is the numeric half of the gate and the reviewer's ground truth.
- **`paper-forge gate`** — convenience: run `compile --strict` + `check --strict-literals` +
  `consistency` + `pytest -q`, print a pass/fail report. The editor's candidates must pass it.

## Claude Code assets paper-forge ships (installed by `paper-forge init`)

```
.claude/
  agents/
    manuscript-reviewer.md   # read-only reviewer subagent (Read/Grep/Bash only)
    manuscript-editor.md     # editor subagent — edits template + units only, worktree isolation
  skills/
    paper-review/SKILL.md    # /paper-review — orchestrates one review (M0) → the loop (M3)
manuscript/review/
    rubric.md                # journal rubric + persona(s) + project-specific known concerns
```

## Control flow (the skill; a `Workflow` once the user opts into orchestration)

```
1. paper-forge gate            # must be green before we review anything (Bash)
2. paper-forge review-context  # bundle manuscript + rubric + provenance (Bash)
3. spawn manuscript-reviewer   # Agent tool → structured findings + rubric score
4. paper-forge consistency     # auto-drop any "wrong number" finding the JSON contradicts
5. present findings (M0 stops here) — ranked, each grounded in a line + provenance ref
   ── loop (M3+): ──
6. spawn manuscript-editor on top findings (worktree) → minimal diff to template/units
7. paper-forge gate on the candidate → reject if red
8. re-spawn reviewer → keep iff score improved (autoresearch keep/discard), else discard
9. accepted diffs land as commits on a review branch; repeat until plateau / budget
```

## Milestones

- **M0 — Reviewer, read-only.** rubric + `manuscript-reviewer` subagent + `review-context`.
  `/paper-review` compiles, spawns the reviewer, prints structured findings + score. Calibrate
  against Daniele's `docs/v19_review/peer_review.md`. *No editing.*
- **M1 — Consistency gate.** `paper-forge consistency` + `gate`; wire into `/paper-review` so
  the reviewer's numeric claims are auto-verified (it can't hallucinate a discrepancy).
- **M2 — Editor + gate, one round, human-approved.** `manuscript-editor` subagent proposes a
  minimal diff for the top finding (worktree isolation); gate it; show the diff for approval.
- **M3 — Loop.** The skill (or a `Workflow`) runs review→edit→gate→keep/discard with plateau
  detection + a token budget; accepted diffs commit to a `review/<date>` branch.
- **M4 — `/paper-review --auto`.** Overnight loop; a human merges the review-branch PR.

## Data-analyst agent + scope control (the "reviewers always want more" problem)

The editor splits in two by *what it touches*: **prose-editor** (framing/clarity → template
prose) and **data-analyst** (analysis → result units, gate-verified). The analyst is the risky
one — reviewers ask for endless analysis, and doing all of it balloons the paper and opens new
attack surface. It is scope-limited **by construction**, not by intent:

1. **Triage every analysis ask into fix / strengthen / expand, default-deny on expand.**
   *fix* = correct a computation the paper already reports (auto). *strengthen* = add rigor
   (CI/test/sensitivity) to an existing claim over the same data+features (human-approve).
   *expand* = new data/colonies/features/models (propose only — a rebuttal note; nothing runs).
2. **Analysis charter** (`manuscript/review/charter.md`) declares in-scope data/features/models;
   the analyst may operate only inside it. Amending it is a deliberate human act — that's the
   valve that lets the analysis grow.
3. **The paper-forge invariant bounds it structurally** — a number can change only via a gated
   result unit that runs against the declared data. No hand-waved results.
4. **Data-access reality + budget** — asks needing data it can't read downgrade to a rebuttal
   note; ≤ 3 changed units per round.
5. **Net-benefit gate** — keep only if re-review shows the paper got stronger and no new weakness
   opened (catches the significance-paragraph-that-backfires case).

Invocation: `/paper-analyze` triages `/paper-review` findings and routes them; or `/paper-analyze
<finding-id>` on one. Assets: `.claude/agents/data-analyst.md`, `.claude/skills/paper-analyze/`,
`manuscript/review/charter.md`.

## Testing

- paper-forge pieces (`consistency`, `review-context`, `gate`) get pytest coverage with
  fixture manuscripts — deterministic, no LLM in the test path.
- The reviewer/editor subagents are validated by running them on the reservoir manuscript and
  checking they surface the known issues in `peer_review.md` (calibration, not unit tests).

## First step

Build **M0** and run the reviewer subagent on the reservoir manuscript now, calibrating its
findings against `docs/v19_review/peer_review.md`. Reviewer runs as a Claude Code subagent —
no API key, no external call.
