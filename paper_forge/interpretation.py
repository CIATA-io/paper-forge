"""Configurable interpretation engine for statistical results.

The interpretation engine transforms raw statistical values (p-values,
effect sizes, etc.) into verbal phrases suitable for scientific manuscripts.
Rules are defined in YAML and can be extended with custom functions.

Example YAML rules::

    rules:
      dance_duration_effect:
        function: correlation_effect
        args:
          p_key: "dance.p_duration"
          rho_key: "dance.rho_duration"
          pos_verb: "increases"
          neg_verb: "decreases"
        output_key: "dance_duration_interp"
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

import yaml


# ---------------------------------------------------------------------------
# Built-in interpretation functions
# ---------------------------------------------------------------------------

def correlation_effect(
    p: float,
    rho: float,
    pos_verb: str = "increases",
    neg_verb: str = "decreases",
    alpha: float = 0.05,
) -> str:
    """Generate a verbal phrase describing a correlation effect.

    Args:
        p: P-value of the correlation.
        rho: Correlation coefficient (e.g. Spearman's rho).
        pos_verb: Verb to use for positive correlations.
        neg_verb: Verb to use for negative correlations.
        alpha: Significance threshold.

    Returns:
        A phrase like ``"significantly increases"`` or
        ``"does not significantly change"``.

    Examples:
        >>> correlation_effect(0.001, 0.5, "increases", "decreases")
        'significantly increases'
        >>> correlation_effect(0.2, -0.1, "increases", "decreases")
        'does not significantly change'
    """
    if _is_missing(p) or _is_missing(rho):
        return "N/A"

    if p < alpha:
        verb = pos_verb if rho > 0 else neg_verb
        return f"significantly {verb}"
    return "does not significantly change"


def correlation_qualifier(
    p: float,
    rho: float,
    alpha: float = 0.05,
) -> str:
    """Generate a qualifier phrase for a correlation result.

    Combines significance with effect size magnitude to produce phrases
    like "This strong positive effect" or "This non-significant result".

    Args:
        p: P-value.
        rho: Correlation coefficient.
        alpha: Significance threshold.

    Returns:
        A qualifier phrase for use in discussion sections.

    Examples:
        >>> correlation_qualifier(0.001, 0.7)
        'This strong positive effect'
        >>> correlation_qualifier(0.3, 0.1)
        'This non-significant result'
    """
    if _is_missing(p) or _is_missing(rho):
        return "N/A"

    if p >= alpha:
        return "This non-significant result"

    abs_rho = abs(rho)
    if abs_rho >= 0.5:
        strength = "strong"
    elif abs_rho >= 0.3:
        strength = "moderate"
    elif abs_rho >= 0.1:
        strength = "weak"
    else:
        strength = "very weak"

    direction = "positive" if rho > 0 else "negative"
    return f"This {strength} {direction} effect"


def comparison(
    p1: float,
    rho1: float,
    p2: float,
    rho2: float,
    label1: str = "the first",
    label2: str = "the second",
    alpha: float = 0.05,
) -> str:
    """Compare two correlation effects verbally.

    Args:
        p1: P-value of the first correlation.
        rho1: Effect size of the first correlation.
        p2: P-value of the second correlation.
        rho2: Effect size of the second correlation.
        label1: Label for the first effect.
        label2: Label for the second effect.
        alpha: Significance threshold.

    Returns:
        A comparative phrase describing the two effects.

    Examples:
        >>> comparison(0.001, 0.6, 0.2, 0.1, "duration", "frequency")
        'duration shows a significant effect while frequency does not'
    """
    sig1 = p1 < alpha if not _is_missing(p1) else False
    sig2 = p2 < alpha if not _is_missing(p2) else False

    if sig1 and sig2:
        if abs(rho1) > abs(rho2):
            return f"both {label1} and {label2} show significant effects, with {label1} showing a stronger effect"
        elif abs(rho2) > abs(rho1):
            return f"both {label1} and {label2} show significant effects, with {label2} showing a stronger effect"
        else:
            return f"both {label1} and {label2} show significant effects of similar magnitude"
    elif sig1 and not sig2:
        return f"{label1} shows a significant effect while {label2} does not"
    elif not sig1 and sig2:
        return f"{label2} shows a significant effect while {label1} does not"
    else:
        return f"neither {label1} nor {label2} shows a significant effect"


def significance_stars(p: float) -> str:
    """Return significance stars for a p-value.

    This is a simpler alias that can be used directly as an interpretation
    function (as opposed to the formatter ``fmt_p_stars``).

    Args:
        p: The p-value.

    Returns:
        ``'***'``, ``'**'``, ``'*'``, or ``'n.s.'``
    """
    if _is_missing(p):
        return "N/A"
    p = float(p)
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _is_missing(x: object) -> bool:
    """Check if a value is None or NaN."""
    if x is None:
        return True
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Built-in function registry
# ---------------------------------------------------------------------------

_BUILTIN_FUNCTIONS: dict[str, Callable[..., str]] = {
    "correlation_effect": correlation_effect,
    "correlation_qualifier": correlation_qualifier,
    "comparison": comparison,
    "significance_stars": significance_stars,
}


# ---------------------------------------------------------------------------
# Interpretation Engine
# ---------------------------------------------------------------------------

class InterpretationEngine:
    """Engine that applies interpretation rules to statistical results.

    The engine loads rules from a YAML configuration and applies them
    to resolve interpretation placeholders in manuscripts.

    Each rule maps input keys (from result units) to an interpretation
    function that produces a verbal phrase.

    Attributes:
        rules: Dictionary of loaded interpretation rules.
        functions: Dictionary of available interpretation functions.
    """

    def __init__(self) -> None:
        self.rules: dict[str, dict[str, Any]] = {}
        self.functions: dict[str, Callable[..., str]] = dict(_BUILTIN_FUNCTIONS)

    def load_rules(self, yaml_path: str | Path) -> None:
        """Load interpretation rules from a YAML file.

        The YAML file should have a top-level ``rules`` key containing
        a mapping of rule names to their configurations.

        Args:
            yaml_path: Path to the YAML rules file.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError: If the YAML structure is invalid.

        Examples:
            >>> engine = InterpretationEngine()
            >>> engine.load_rules("interpretations.yaml")
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Interpretation rules file not found: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict) or "rules" not in config:
            raise ValueError(
                f"Invalid interpretation rules file {yaml_path}: "
                "expected a top-level 'rules' key"
            )

        for name, rule in config["rules"].items():
            if "function" not in rule:
                raise ValueError(
                    f"Rule '{name}' in {yaml_path} is missing required 'function' key"
                )
            if rule["function"] not in self.functions:
                raise ValueError(
                    f"Rule '{name}' references unknown function '{rule['function']}'. "
                    f"Available: {list(self.functions.keys())}"
                )
            self.rules[name] = rule

    def register_function(self, name: str, func: Callable[..., str]) -> None:
        """Register a custom interpretation function.

        Args:
            name: Name to reference in YAML rules.
            func: Function that takes keyword arguments and returns a string.

        Examples:
            >>> engine = InterpretationEngine()
            >>> engine.register_function("my_interp", lambda p: "sig" if p < 0.05 else "ns")
        """
        self.functions[name] = func

    def resolve(
        self,
        rule_name: str,
        all_results: dict[str, Any],
    ) -> str:
        """Resolve a single interpretation rule against loaded results.

        Looks up the rule by name, extracts the required values from the
        results dictionary, and calls the interpretation function.

        Args:
            rule_name: Name of the rule to resolve.
            all_results: Flat dictionary of all available results
                (prefix.key → value).

        Returns:
            The interpretation string.

        Raises:
            KeyError: If the rule name is not found.
            KeyError: If a required result key is not found.
        """
        if rule_name not in self.rules:
            raise KeyError(f"Unknown interpretation rule: '{rule_name}'")

        rule = self.rules[rule_name]
        func_name = rule["function"]
        func = self.functions[func_name]
        args_spec = rule.get("args", {})

        # Resolve argument values from results
        kwargs: dict[str, Any] = {}
        for param_name, param_value in args_spec.items():
            if param_name.endswith("_key"):
                # This is a reference to a result key
                actual_param = param_name[:-4]  # strip "_key" suffix
                if param_value not in all_results:
                    raise KeyError(
                        f"Interpretation rule '{rule_name}' references key "
                        f"'{param_value}' which was not found in results. "
                        f"Available keys: {sorted(all_results.keys())[:20]}"
                    )
                kwargs[actual_param] = all_results[param_value]
            else:
                # Literal value
                kwargs[param_name] = param_value

        return func(**kwargs)

    def resolve_all(
        self,
        all_results: dict[str, Any],
    ) -> dict[str, str]:
        """Resolve all loaded interpretation rules.

        Args:
            all_results: Flat dictionary of all available results.

        Returns:
            Dictionary mapping output keys to interpretation strings.
        """
        outputs: dict[str, str] = {}
        for rule_name, rule in self.rules.items():
            output_key = rule.get("output_key", rule_name)
            try:
                outputs[output_key] = self.resolve(rule_name, all_results)
            except KeyError as e:
                outputs[output_key] = f"[INTERP ERROR: {e}]"
        return outputs


def load_rules(yaml_path: str | Path) -> InterpretationEngine:
    """Convenience function to create an engine and load rules.

    Args:
        yaml_path: Path to the YAML rules file.

    Returns:
        Configured InterpretationEngine with rules loaded.

    Examples:
        >>> engine = load_rules("interpretations.yaml")
        >>> result = engine.resolve("my_rule", {"p": 0.01, "rho": 0.5})
    """
    engine = InterpretationEngine()
    engine.load_rules(yaml_path)
    return engine
