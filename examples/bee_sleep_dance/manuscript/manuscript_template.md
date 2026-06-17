---
title: "Sleep Deprivation Effects on Honeybee Dance Communication"
author:
  - name: "Example Author"
    affiliation: "Freie Universität Berlin"
date: "2026"
abstract: |
  We investigated the effects of sleep deprivation on waggle dance communication
  accuracy in honeybees (Apis mellifera). A total of {{pop.n_total:int}} bees
  from {{pop.n_colonies:int}} colonies were assigned to sleep-deprived
  (n = {{pop.n_deprived:int}}) or control (n = {{pop.n_control:int}}) conditions.
  Sleep-deprived bees showed {{pop.mean_error_deprived:f1}}° ± {{pop.sd_error_deprived:f1}}°
  mean dance error compared to {{pop.mean_error_control:f1}}° ± {{pop.sd_error_control:f1}}°
  in controls ({{pop.dance_p:p}}, r = {{pop.dance_r:r}}).
  {{pop.dance_interp}}
---

# Introduction

The honeybee waggle dance is a sophisticated communication system that encodes
the distance and direction of food sources. Sleep is thought to play an
important role in neural function, yet the effects of sleep deprivation on
dance communication accuracy remain poorly understood.

We hypothesized that sleep deprivation would impair dance communication
accuracy and that this effect would be strongest in the morning hours
following a sleepless night.

# Methods

## Animals and Design

We tested {{pop.n_total:int}} forager bees from {{pop.n_colonies:int}} colonies.
Bees were randomly assigned to sleep-deprived (n = {{pop.n_deprived:int}})
or control (n = {{pop.n_control:int}}) conditions. Sleep deprivation was
achieved via gentle mechanical stimulation throughout the night.

## Analysis

Dance accuracy was quantified as the angular error (degrees) between the
waggle run direction and the true food source direction. Group differences
were assessed with Mann–Whitney U tests. Temporal patterns were analyzed
across {{temp.n_observations:int}} observation sessions.

# Results

## Population-Level Effects

Sleep-deprived bees (Mdn = {{pop.median_error_deprived:f1}}°) showed
larger dance errors than controls (Mdn = {{pop.median_error_control:f1}}°;
U = {{pop.dance_u:f1}}, {{pop.dance_p:p}}, r = {{pop.dance_r:r}}).
{{pop.dance_interp}}

{{pop.mass_interp}}

## Temporal Patterns

The sleep deprivation effect was stronger in morning sessions
(M = {{temp.mean_effect_morning:f1}}° ± {{temp.sd_effect_morning:f1}}°)
than afternoon sessions
(M = {{temp.mean_effect_afternoon:f1}}° ± {{temp.sd_effect_afternoon:f1}}°;
U = {{temp.temporal_u:f1}}, {{temp.temporal_p:p}}, r = {{temp.temporal_r:r}}).
{{temp.temporal_interp}}

Additionally, dance error was correlated with time since waking
(ρ = {{temp.correlation_rho:r}}, {{temp.correlation_p:p}},
n = {{temp.n_correlation:int}}).
{{temp.correlation_interp}}

# Discussion

{{pop.dance_interp}} The effect was modulated by time of day:
{{temp.temporal_interp}}

These findings suggest that sleep plays an important role in maintaining
the accuracy of honeybee dance communication, with implications for our
understanding of sleep function in insects.

# References
