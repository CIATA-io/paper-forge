---
title: "Analysis of Treatment Effects in a Controlled Experiment"
author:
  - name: "Author One"
    affiliation: "Department of Science, University of Examples"
  - name: "Author Two"
    affiliation: "Institute for Reproducible Research"
date: "2026"
abstract: |
  We investigated treatment effects in a sample of {{ex.n_total:int}} subjects
  randomly assigned to treatment (n = {{ex.n_treatment:int}}) and control
  (n = {{ex.n_control:int}}) groups. The treatment {{interp.main_effect}}
  the outcome relative to controls
  (effect size r = {{ex.effect_size:r}}, {{ex.main_p:p}}).
keywords:
  - reproducible research
  - statistical analysis
  - paper-forge
---

# Introduction

Reproducibility is a cornerstone of scientific research. Yet, transcription errors
in reporting statistical results remain common. This paper demonstrates a fully
reproducible pipeline where all reported numbers are generated directly from
analysis code, eliminating manual transcription.

We hypothesized that the treatment would produce measurably different outcomes
compared to a control condition.

# Methods

## Participants

We recruited {{ex.n_total:int}} participants from the university subject pool.
Participants were randomly assigned to either the treatment group
(n = {{ex.n_treatment:int}}) or the control group (n = {{ex.n_control:int}}).

## Procedure

Each participant completed a standardized assessment battery before and after
the intervention period. The treatment group received the experimental
intervention over a 4-week period, while the control group received a <!-- pf-allow-literal: study protocol, fixed by design -->
placebo intervention matched for duration and contact time.

## Statistical Analysis

Group differences were assessed using a Mann–Whitney U test due to the
non-normal distribution of outcome scores. Effect sizes are reported as
rank-biserial correlation (r). All analyses were conducted in Python using
the paper-forge reproducible pipeline. The significance threshold was set
at α = 0.05. <!-- pf-allow-literal: the alpha this analysis declares -->

# Results

## Primary Outcome

A Mann–Whitney U test showed that the treatment
(Mdn = {{ex.median_treatment:fmt2}}) {{interp.main_effect}} the control group
(Mdn = {{ex.median_control:fmt2}}; U = {{ex.u_statistic:fmt1}}, {{ex.main_p:p}},
r = {{ex.effect_size:r}}, {{interp.main_stars}}).

## Descriptive Statistics

Treatment group: M = {{ex.mean_treatment:fmt2}}, SD = {{ex.sd_treatment:fmt2}}.
Control group: M = {{ex.mean_control:fmt2}}, SD = {{ex.sd_control:fmt2}}.

The overall response rate was {{ex.response_rate:pct}}.

# Discussion

{{interp.main_qualifier}}, with an observed effect size of
{{ex.effect_size:r}}, frames how much practical impact to expect.

These results are consistent with prior work showing that targeted
interventions can produce measurable changes in the outcome variable.
The fully reproducible analysis pipeline ensures that all reported statistics
can be independently verified by re-running the analysis code.

## Limitations

The sample size of {{ex.n_total:int}} participants, while adequate for
detecting medium-to-large effects, may be underpowered for detecting small
effects. Future studies should consider larger samples.

# Conclusion

Tested against the hypothesized treatment effect, the analysis found that the
treatment {{interp.main_effect}} the outcome. All numbers and every verdict in
this manuscript were generated directly from analysis code, ensuring zero
transcription errors.

# References
