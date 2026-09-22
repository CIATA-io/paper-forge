# `/draft_template` — Author the Manuscript Template

> Write `manuscript/manuscript_template.md` from the research questions and the result
> units. The output is a template: prose whose every number and every verdict is a
> placeholder, so the manuscript re-derives itself whenever the analysis changes.

You are drafting **Layer 2**. Layers 1 (result units) and 3 (the compiler) already exist.
Your job is the prose that connects them — and the one way to get it wrong that no
downstream check used to catch.

---

## The rule that matters most

**A verdict is not yours to write.**

A *verdict* is any claim whose truth depends on a statistic: "significant", "did not
differ", "predicts", "stronger than", "no association". You will have the result JSONs
open while you draft. It is natural to read `p = 0.031`, judge it marginal, and write
"dancers did not differ appreciably from controls." That sentence is now **frozen at
today's data**. Change the stillness threshold, add a season, fix a bug upstream — the
p-value next to it updates, because it is a placeholder, and the claim around it does not.

This is not a hypothetical failure. It is why paper-forge exists.

So:

> **Read result values to learn which keys exist. Never to decide what to claim.**

A useful self-test while drafting each sentence:

> *If this p-value crossed 0.05 tomorrow, would I have to re-word this sentence?*

If yes, the wording must come from an interpretation rule, not from you.

---

## Phase 1 — Scope: read the research questions first

The RQ registry, not the results directory, defines what the paper argues.

```bash
cat manuscript/research_questions.md
```

Build the spine before writing a word of prose:

| RQ | Question | Status | Units |
|----|----------|--------|-------|
| RQ1 | … | open | 01_population |

Rules:

- Every `open` / `answered` question gets reported. A question with no home in the
  manuscript is a gap — say so rather than quietly dropping it.
- Every claim you write traces to exactly one RQ. If you cannot name the RQ a sentence
  serves, the sentence is scope creep — cut it.
- Do **not** add research questions to fit results you find interesting. Growing scope is
  a deliberate edit to the registry, by a human.
- Units declaring `rq="methods"` are descriptive; they populate Methods, not Results.

## Phase 2 — Inventory the result units by *schema*

You need the key names and types. You do not need to internalise the values.

```bash
for f in manuscript/results/*.json; do
  echo "=== $(basename "$f") ==="
  uv run python -c "
import json, sys
with open(sys.argv[1]) as fh:
    d = json.load(fh).get('results', {})
for k, v in sorted(d.items()):
    print(f'  {k}: {type(v).__name__}')
" "$f"
done
```

This deliberately prints types, not values — it is the schema you are wiring to. When you
do need a value (deciding whether a table row exists at all, say), read it, then
consciously set it aside before writing the sentence.

Map each unit to its placeholder prefix from `project.yaml`:

| JSON | Prefix | Keys | Serves RQ |
|------|--------|------|-----------|
| 01_population.json | pop | n_total, … | methods |

## Phase 3 — Declare interpretation rules *before* writing prose

This ordering is the point. You cannot write "dance significantly predicts sleep" if the only
way *you* may say it is `{{interp.dance_sleep}}` and that rule does not exist yet. paper-forge
also lets a result unit emit the phrase itself (README option 1), but that route is closed to
you here: a verdict you wrote after reading the data is one the data chose for you. The
frozen-verdict guard will catch a verdict string that is not inside a branch, but declaring the
rule first is what stops the data choosing your wording in the first place.

For every verdict the paper needs, add a rule to `interpretations.yaml`:

```yaml
rules:
  dance_sleep:
    function: correlation_effect
    output_key: dance_sleep
    args:
      p_key: temp.wb_p
      rho_key: temp.wb_rho
      pos_verb: predicts more
      neg_verb: predicts less
```

Built-ins: `correlation_effect`, `correlation_qualifier`, `comparison`,
`significance_stars`.

Most papers need at least one verdict those cannot express — a multi-branch
directionality summary, a Title Case variant for a heading, a domain-specific
comparison. Write it as a Python function rather than as prose:

```python
# scripts/interp_functions.py
def directionality(fwd_p, rev_p, alpha=0.05):
    fwd, rev = fwd_p < alpha, rev_p < alpha
    if fwd and rev:
        return "is bidirectional"
    if fwd:
        return "runs one way only: dance drives sleep"
    ...

def register(engine):
    engine.register_function("directionality", directionality)
```

```yaml
# project.yaml
interpretation_functions: scripts/interp_functions.py
```

The rule then uses `function: directionality` like any built-in. Write the function; do
not write the branch into the prose.

**The rule owns the whole verbal claim, not a fragment.** Fragments recombine wrongly:

```markdown
<!-- WRONG — "is" + a verb phrase is ungrammatical the moment the verdict flips -->
The reverse effect is {{interp.reverse}}: sleep → dance.

<!-- RIGHT — the rule emits a clause that stands on its own in every branch -->
Sleep {{interp.reverse_sleep_dance}} next-day dancing.
```

Check every branch your rule can emit and read the sentence aloud in each. A rule that
reads well when significant and garbles when null is not finished.

## Phase 4 — Write the template, covering every section

Numbers → `{{prefix.key:formatter}}`. Verdicts → `{{interp.key}}`.

### A bound is a claim, not a number

When a placeholder sits next to `<`, `>`, `≤`, `≥`, or at either end of a range, you
are not reporting a value — you are asserting that no data point falls outside it.
Two things have to be right.

**Wire the extreme, not a member.** `all p < {{ctrl.total_sleep_p:p}}` is false the
moment a sibling p-value exceeds it. Wire the max of the family (a `derived:` key with
`max(...)` if none exists), not whichever key you happened to be looking at.

**Round away from the data.** `f0`–`f3` round to nearest and will silently flip the
claim: `max |d| < {{k:f1}}` on 0.234 renders `< 0.2`, and `all p > {{k:f2}}` on 0.3453
renders `> 0.35`. Both are contradicted by the value they came from. Use `:Nceil`
after `<` / `≤` and `:Nfloor` after `>` / `≥`.

`gate` cannot catch either mistake — the number is correctly wired and correctly
rendered, so only the surrounding sentence is wrong.

### Coverage is the requirement

A verdict is stated in **more than one place**. A finding typically appears in the
abstract, in Results, in the Discussion summary, and in a figure caption. If you wire the
Results sentence to an interpretation rule and hand-write the other three, you have built
a manuscript that contradicts itself on a re-run — and the contradiction is *harder* to
spot, because the freshly-derived half looks trustworthy.

**For each RQ, wire every one of these that exists:**

- [ ] Abstract sentence
- [ ] Results paragraph
- [ ] Results table cell (verdict columns and significance stars)
- [ ] Discussion summary point
- [ ] Figure caption — inline `![...](...)` alt text *and* any Figure Legends section
- [ ] Supplementary text

Figure captions and the abstract are where this fails most often. They read like framing
rather than results reporting, so they get hand-written. They are results reporting.

### Section-by-section

**Title.** If the title states a finding ("X Predicts Y, but Y Only Weakly Predicts X"),
it is a verdict and must be built from an interpretation rule. A title that hardcodes a
result the data no longer supports is the most expensive version of this bug.

**Abstract.** Every number a placeholder, every verdict an `{{interp.*}}`. No exceptions
because "it's just a summary".

**Introduction.** Mostly static. Claims about published work are exempt and need no
placeholder — but only when the sentence cites a key that **resolves** to a real entry in
the project's `.bib`. Writing `(Klein et al. 2010)` in the prose exempts nothing and is
reported as an unkeyed attribution: it cites nothing, citeproc ignores it, and it never
reaches the reference list. So cite only keys you have read in the `.bib`; where you need a
source you do not have, leave `<!-- TODO(cite): ... -->` and say so. With reference
tokens the rule is sharper still: a token is derived from its entry, so one you did not
copy from `paper-forge tokens` cannot resolve — composing one is fabrication by
construction, and the gate names it as such. End with the questions
from Phase 1, phrased as questions, not as answers.

**Methods.** Static prose plus placeholders for anything derived: sample sizes, thresholds,
window boundaries, counts. If a parameter appears in a result JSON (`threshold_cms`), cite
it as a placeholder — do not retype the value, or Methods will drift from the analysis it
describes.

**Results.** One subsection per RQ, in registry order. Per finding:

```markdown
Dancers (Mdn = {{ctrl.dancer_med:f1}} s) {{interp.ctrl_total_sleep}} controls
(Mdn = {{ctrl.control_med:f1}} s; U = {{ctrl.u:f1}}, p = {{ctrl.p:p}},
r = {{ctrl.r:r}}).
```

Section headings state verdicts too. Prefer a neutral heading ("Dancers versus
network-matched controls") over one that bakes in an answer, unless the heading is itself
built from a rule.

**Discussion.** Open with `{{interp.*_qualifier}}` rather than asserting the strength
yourself. Interpretation of *mechanism* — what the effect might mean — is yours to write;
restating *whether* the effect holds is not.

**Figure legends.** Same rules. Wire them.

## Phase 5 — Verify

```bash
paper-forge gate
```

Six deterministic checks, all must pass:

1. **strict compile** — every placeholder resolves
2. **numeric-literal guard** — no hardcoded numbers
3. **verdict-claim guard** — no hardcoded verdicts in the template
4. **frozen-verdict guard** — no verdict a result unit states instead of deriving
5. **citation guard** — every cite key and `[ref:…]` token resolves; no attribution
   written as bare prose; a draft bibliography produces `unverified-entry` (warning
   by default; fatal when `require_verified: true`)
6. **research-question check** — every unit serves a declared RQ

For findings that are genuinely static, annotate deliberately — never to silence a real
verdict:

```markdown
Colonies were housed at 34 °C. <!-- pf-allow-literal: apparatus constant -->
Sleep deprivation impairs dances. <!-- pf-allow-claim: prior literature, uncited here -->
Follow @nature for updates. <!-- pf-allow-cite: social handle, not a citation -->
```

Reaching for an allow-comment on a claim about *your own* results means the sentence needs
an interpretation rule instead. Recurring exceptions belong in `project.yaml`
(`literals.allow`, `claims.allow`, `citations.allow`) with a comment saying why.

Then confirm you changed where the numbers come from, not what they say:

```bash
paper-forge baseline          # every number must still match the manuscript as adopted
```

An empty result is the point: it says the slots you wired reproduce the paper exactly as
it read before. The guards prove a claim is *wired*; the baseline proves wiring it did not
rewrite the paper. When a number changes because you meant it to, re-record with
`paper-forge baseline --record` and say so — that is the moment the content actually moved.

Then read the compiled output as prose:

```bash
paper-forge compile && cat manuscript/manuscript.md
```

## Phase 6 — Flip the verdicts

The guard proves verdicts are *wired*. It cannot prove they read correctly when they
change. Before declaring the template done, test the branches:

1. Copy `manuscript/results/` aside.
2. Edit a JSON so a key result crosses significance in the opposite direction.
3. `paper-forge compile` and read the affected passages — abstract, results, discussion,
   captions.
4. Confirm every one flipped, and that each still reads as grammatical English.
5. Restore the real results.

Passages that did not change are hand-written verdicts the guard's vocabulary missed. Fix
them, and add the pattern to `claims.extra_patterns` so it is caught next time.

## Completion checklist

- [ ] Every `open` / `answered` RQ is reported somewhere in the manuscript
- [ ] Every claim traces to exactly one RQ
- [ ] Every verdict resolves through `{{interp.*}}` — including abstract, captions, title
- [ ] Every number resolves through `{{prefix.key:formatter}}`
- [ ] Every bound wires the extreme of its family and uses `:Nceil` / `:Nfloor`
- [ ] No result unit states a verdict — rules engine only (frozen-verdict guard checks this)
- [ ] `paper-forge gate` passes
- [ ] Verdict-flip test done: all branches read as grammatical English
- [ ] Compiled manuscript reads as prose, not as a form with numbers slotted in
