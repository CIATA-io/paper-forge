"""Tests for the interpretation engine."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from paper_forge.interpretation import (
    InterpretationEngine,
    comparison,
    correlation_effect,
    correlation_qualifier,
    load_rules,
    significance_stars,
)


class TestCorrelationEffect:
    """Tests for the correlation_effect function."""

    def test_significant_positive(self):
        result = correlation_effect(0.001, 0.5, "increases", "decreases")
        assert result == "significantly increases"

    def test_significant_negative(self):
        result = correlation_effect(0.001, -0.5, "increases", "decreases")
        assert result == "significantly decreases"

    def test_not_significant(self):
        result = correlation_effect(0.2, 0.1, "increases", "decreases")
        assert result == "does not significantly change"

    def test_borderline_significant(self):
        result = correlation_effect(0.05, 0.3, "increases", "decreases")
        assert "does not" in result  # 0.05 is NOT < 0.05

    def test_just_below_alpha(self):
        result = correlation_effect(0.049, 0.3, "increases", "decreases")
        assert "significantly" in result

    def test_custom_alpha(self):
        result = correlation_effect(0.08, 0.3, "increases", "decreases", alpha=0.1)
        assert "significantly" in result

    def test_nan_p(self):
        assert correlation_effect(float("nan"), 0.5, "up", "down") == "N/A"

    def test_none_rho(self):
        assert correlation_effect(0.01, None, "up", "down") == "N/A"


class TestCorrelationQualifier:
    """Tests for the correlation_qualifier function."""

    def test_strong_positive(self):
        result = correlation_qualifier(0.001, 0.7)
        assert "strong" in result
        assert "positive" in result

    def test_strong_negative(self):
        result = correlation_qualifier(0.001, -0.6)
        assert "strong" in result
        assert "negative" in result

    def test_moderate(self):
        result = correlation_qualifier(0.01, 0.35)
        assert "moderate" in result

    def test_weak(self):
        result = correlation_qualifier(0.02, 0.15)
        assert "weak" in result

    def test_very_weak(self):
        result = correlation_qualifier(0.04, 0.05)
        assert "very weak" in result

    def test_not_significant(self):
        result = correlation_qualifier(0.3, 0.1)
        assert "non-significant" in result

    def test_nan(self):
        assert correlation_qualifier(float("nan"), 0.5) == "N/A"


class TestComparison:
    """Tests for the comparison function."""

    def test_first_sig_only(self):
        result = comparison(0.001, 0.6, 0.2, 0.1, "duration", "frequency")
        assert "duration" in result
        assert "significant" in result
        assert "frequency does not" in result

    def test_second_sig_only(self):
        result = comparison(0.2, 0.1, 0.001, 0.6, "duration", "frequency")
        assert "frequency" in result
        assert "significant" in result

    def test_both_sig_first_stronger(self):
        result = comparison(0.001, 0.7, 0.01, 0.3, "A", "B")
        assert "both" in result
        assert "A" in result
        assert "stronger" in result

    def test_both_sig_second_stronger(self):
        result = comparison(0.001, 0.3, 0.01, 0.7, "A", "B")
        assert "both" in result
        assert "B" in result
        assert "stronger" in result

    def test_both_sig_equal(self):
        result = comparison(0.001, 0.5, 0.01, 0.5, "A", "B")
        assert "similar magnitude" in result

    def test_neither_sig(self):
        result = comparison(0.2, 0.1, 0.3, 0.05, "A", "B")
        assert "neither" in result


class TestSignificanceStars:
    """Tests for the significance_stars function."""

    def test_three_stars(self):
        assert significance_stars(0.0001) == "***"

    def test_two_stars(self):
        assert significance_stars(0.005) == "**"

    def test_one_star(self):
        assert significance_stars(0.03) == "*"

    def test_ns(self):
        assert significance_stars(0.1) == "n.s."

    def test_nan(self):
        assert significance_stars(float("nan")) == "N/A"


class TestInterpretationEngine:
    """Tests for the InterpretationEngine class."""

    @pytest.fixture
    def rules_yaml(self, tmp_path: Path) -> Path:
        """Create a temporary YAML rules file."""
        rules = {
            "rules": {
                "effect_test": {
                    "function": "correlation_effect",
                    "args": {
                        "p_key": "stats.p",
                        "rho_key": "stats.rho",
                        "pos_verb": "grows",
                        "neg_verb": "shrinks",
                    },
                    "output_key": "effect_text",
                },
                "qualifier_test": {
                    "function": "correlation_qualifier",
                    "args": {
                        "p_key": "stats.p",
                        "rho_key": "stats.rho",
                    },
                    "output_key": "qualifier_text",
                },
            }
        }
        path = tmp_path / "rules.yaml"
        path.write_text(yaml.dump(rules))
        return path

    def test_load_rules(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)
        assert "effect_test" in engine.rules
        assert "qualifier_test" in engine.rules

    def test_resolve_single(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        results = {"stats.p": 0.001, "stats.rho": 0.6}
        text = engine.resolve("effect_test", results)
        assert text == "significantly grows"

    def test_resolve_negative(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        results = {"stats.p": 0.001, "stats.rho": -0.6}
        text = engine.resolve("effect_test", results)
        assert text == "significantly shrinks"

    def test_resolve_all(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        results = {"stats.p": 0.001, "stats.rho": 0.6}
        outputs = engine.resolve_all(results)
        assert "effect_text" in outputs
        assert "qualifier_text" in outputs
        assert "significantly grows" in outputs["effect_text"]
        assert "strong" in outputs["qualifier_text"]

    def test_missing_key_in_resolve(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        results = {"stats.p": 0.001}  # Missing stats.rho
        with pytest.raises(KeyError, match="stats.rho"):
            engine.resolve("effect_test", results)

    def test_resolve_all_handles_errors_gracefully(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        results = {"stats.p": 0.001}  # Missing stats.rho
        outputs = engine.resolve_all(results)
        assert "INTERP ERROR" in outputs["effect_text"]

    def test_unknown_rule(self, rules_yaml: Path):
        engine = InterpretationEngine()
        engine.load_rules(rules_yaml)

        with pytest.raises(KeyError, match="nonexistent"):
            engine.resolve("nonexistent", {})

    def test_missing_rules_file(self, tmp_path: Path):
        engine = InterpretationEngine()
        with pytest.raises(FileNotFoundError):
            engine.load_rules(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_structure(self, tmp_path: Path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("just: a string")
        engine = InterpretationEngine()
        with pytest.raises(ValueError, match="rules"):
            engine.load_rules(bad_yaml)

    def test_unknown_function_in_rules(self, tmp_path: Path):
        rules = {"rules": {"bad": {"function": "nonexistent_func"}}}
        path = tmp_path / "bad_rules.yaml"
        path.write_text(yaml.dump(rules))

        engine = InterpretationEngine()
        with pytest.raises(ValueError, match="nonexistent_func"):
            engine.load_rules(path)

    def test_register_custom_function(self):
        engine = InterpretationEngine()
        engine.register_function("custom", lambda x: f"result={x}")
        assert "custom" in engine.functions

    def test_load_rules_convenience(self, rules_yaml: Path):
        engine = load_rules(rules_yaml)
        assert isinstance(engine, InterpretationEngine)
        assert len(engine.rules) == 2
