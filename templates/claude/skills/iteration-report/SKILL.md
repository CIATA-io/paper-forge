---
name: iteration-report
description: Produce the end-of-iteration report for a human running a paper-forge loop, immediately before prompting them to continue. Emits a decision queue — if it is empty the human can continue without reading further — and HALTS the loop on any conclusion-changing change. Use at the end of every loop iteration that touched result units, the template, or the RQ registry. Requires paper-forge gate, git, and the rq_delta.py helper shipped beside this file.
---

# iteration-report

The report a human reads to stay effective in a paper-forge loop. Its one job is to surface
**decisions**, not to narrate activity. Litmus test: **if the decision queue is empty, the
human can say "continue" without reading the rest.** If you find yourself writing what you
did instead of what needs them, you are writing the wrong document.

## Two hard rules

**1. Facts from tools, never from vibes.** Every factual line — a gate result, a number that
moved, a verdict that changed — is copied from a tool's output, tagged with its source
(`[gate]`, `[rq_delta]`, `[git]`). You narrate only *intent* ("re-ran unit 03 because the
threshold moved") and the *next step*. You never assert a delta a tool did not report. The
halt decision in particular is **computed by `rq_delta.py`**, not read by eye from a diff.

**2. Halt on a conclusion-changing change.** When any halt condition below fires, the loop is
blocked: write the HALT items and **stop the turn immediately** — no gate summary, no next
step, no "continue" framing. The human resolves it and starts a new turn. A halt you route to
"decision" instead ships a wrong conclusion the human was told they could skip.

## What halts the loop

A change is conclusion-changing — **HALT** — if ANY of these holds. Evaluate all of them and
report every one that fires, not just the first.

| # | Condition | Source |
|---|---|---|
| H1 | `gate` reports **claim-guard FAIL** — a hardcoded verdict in the template | `[gate]` |
| H2 | `gate` reports **`intro-has-retired`** or **`dropped-in-manuscript`** (by name, whatever severity label gate prints) | `[gate]` |
| H3 | `rq_delta.py` classifies any evidence key **HALT** (headline effect: sign flip, emergence from zero, or ≥25% magnitude shift; headline p-value: crossed alpha) | `[rq_delta]` |
| H4 | A **verdict-word change on a headline/reported RQ** in the compiled manuscript, or **any verdict-word change in the Abstract** | `[git]` |

**Why H1 halts (not a mere fix):** a hardcoded verdict compiles to the *same string every
iteration*, so H4's diff scan can never see it — it could contradict the data forever while
the loop reports "no change". The template must be corrected and recompiled before any halt
condition can be trusted again.

**Why H4 covers the Abstract specially:** the Abstract is the highest-visibility claim in the
paper and often carries verdicts far from any `<!-- rq:ID -->` anchor. A verdict flip there is
the most damaging one possible, so any verdict-word change inside the Abstract section halts,
anchored or not.

## What is a decision (needs the human, does not halt)

- `gate` FAIL on **strict-compile**, **literal-guard**, or **citation-guard** — must fix, but no conclusion moved.
- `check-rqs` **headline-weak** (a headlined RQ on weak/negligible evidence — the framing call),
  **buried-signal**, or **headline-absent** (which also blinds H4 for that RQ — see Notes).
- `rq_delta.py` **DECISION** rows (reported-RQ movements; new headline evidence keys with no
  baseline; large moves on non-verdict headline quantities).
- Any tool the run needed but could not certify (baseline missing, delta extraction failed).

## What is a notification (bury; omit the section if empty)

Advisories on `future_work`/`reported` RQs that meet no decision rule; p-value moves that
stayed the same side of alpha; sub-threshold effect changes; verdict-word changes not
attributable to any RQ anchor.

## Steps

1. **Preflight the diff window.** Run `git status --short manuscript/results manuscript/manuscript.md`.
   The report compares the working tree against **HEAD**, so HEAD must be the previous
   iteration. If tracked result/manuscript changes from an *earlier, uncommitted* iteration are
   present, the diff spans more than one iteration and H3/H4 are unreliable → emit a **DECISION**
   ("commit the prior iteration first") and do not certify halts this run.

2. **Gather deterministic facts** (do not paraphrase — capture verbatim, tagged):
   - `paper-forge gate` → `[gate]`. For H2, scan findings for the literal strings
     `intro-has-retired` / `dropped-in-manuscript` by **name**, regardless of the severity word
     gate prints. Record each of the four checks' PASS/FAIL and the `check-rqs` per-RQ findings
     (ADVISORY/ERROR) separately — gate speaks PASS/FAIL, check-rqs speaks ADVISORY/ERROR; keep
     the two vocabularies in their own columns.
   - `python .claude/skills/iteration-report/rq_delta.py` → `[rq_delta]`. This is the sole
     source for H3. Exit 2 = a halt-class row exists; exit 1 = it could not certify (missing
     baseline) → that is a DECISION, never treat it as "no change".
   - `git diff -U50 manuscript/manuscript.md` → `[git]`, for H4. Use **-U50** so anchor lines
     sit inside their hunks; the default -U3 hides anchors far from an edit.

3. **Scan the compiled diff for verdict flips (H4).** In the `-U50` diff, a line is a
   verdict-flip candidate when a removed (−) and an added (+) line within **30 manuscript lines**
   of a `<!-- rq:ID -->` anchor both carry verdict vocabulary — `significant`, `predicts`,
   `differs`, `increases`, `reduces`, `associated`, their negations, and any listed in a
   `<!-- verdict-synonyms: … -->` comment in the template (if absent, you cover only the fixed
   list — note that coverage gap in Notifications). Catch **same-token direction shifts** too
   ("significantly predicts" → "inversely predicts"): any change to a verdict-bearing line
   counts, not only token add/remove. Then:
   - anchor's RQ role is **headline or reported** → **HALT (H4)**.
   - the changed line sits in the **Abstract** section → **HALT (H4)**, anchored or not.
   - the changed line carries a **resolvable citation** — a `\cite{key}`, `[@key]`, or
     `[ref:token]` whose key/token resolves in the bibliography; or, in a project with no
     `.bib`, a numbered `[12]`; or opens
     with "Unlike/Contrary to/In contrast to" — it is prior-work, not our claim → notification.
     (In a `.bib` project, a prose author-year attribution like "(Klein et al. 2010)" that
     matches no bibliography entry is **not** a resolvable citation; do not grant this exemption
     on shape alone — flag the verdict change normally.)
   - role is **future_work**, or the change is unattributable to any anchor → notification.

4. **Build the decision queue.** Assign stable labels as you classify: halts `DQ-H1, DQ-H2 …`,
   decisions `DQ-D1, DQ-D2 …`. Each item is self-contained: the RQ id / check name, a one-line
   reason, the source tag, and — for a halt — a ≤4-line verbatim excerpt from the tool that fired
   it. Order: all HALT items first, then DECISION items.

5. **If any HALT fired: stop here.** Write only the decision queue (HALT items, then any
   decisions), then end the turn. Do not write the sections below. Do not propose a next step.

6. **Otherwise write the full report** in this order and hand back to the human:

```
## Iteration <n> — <one-line what-happened>

### ⟶ Needs you (<K>)                     ← omit body, print "none — safe to continue" if empty
DQ-D1 [RQ1] headlined on a negligible effect (p=.031, |r|=.03) — headline or demote?
      source: [gate] check-rqs · affects: abstract, Fig 2 caption, discussion #1

### Changed this iteration
  verdicts flipped: 0 · headline evidence moved: 0 · gate: 4/4 (2 advisory)   ← all tool-derived

### Gate                                  ← one row per check; two vocab columns
  check            PASS/FAIL   check-rqs signal
  strict-compile   PASS        —
  literal-guard    PASS        —
  claim-guard      PASS        —
  citation-guard   PASS        —
  check-rqs        PASS        ADVISORY headline-weak(RQ1), headline-absent(RQ3,RQ5)

### RQ delta                              ← only RQs that moved; verbatim from [rq_delta]

### Did & why                             ← one line per change, intent not diff
### Next if you continue                  ← the plan, redirectable before it runs
```

## Notes

- **The empty-queue guarantee is a safety property, not a convenience.** It holds only when
  every `headline-absent` is resolved: a missing anchor blinds H4 for that RQ, so the warning is
  *correct* to repeat every iteration. Do not add an acknowledge/snooze mechanism. If the human
  deliberately defers an anchor, they record it in that RQ's block in `research_questions.md`;
  the standing item stays visible until the anchor exists.
- **H3 vs H4 divide the work.** `rq_delta.py` catches a conclusion change that came from the
  *numbers* moving (same interp rule, new inputs). H4 catches one that came from the *rule*
  changing (same inputs, new verdict wording). Neither subsumes the other; run both.
- **`rq_delta.py` only sees declared evidence.** An RQ with no `evidence:` keys is invisible to
  H3 — its conclusion can only be watched via H4's prose scan. Prefer declaring evidence keys on
  every headline RQ.
- **This skill has no cross-iteration memory.** It compares against HEAD only. Committing each
  accepted iteration is what makes "since last iteration" well-defined; step 1 guards the case
  where that discipline slipped.
