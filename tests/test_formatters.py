"""Tests for the formatters module."""

from __future__ import annotations

import pytest

from paper_forge.formatters import (
    FORMATTERS,
    fmt_f0,
    fmt_f1,
    fmt_f2,
    fmt_f3,
    fmt_hr,
    fmt_int,
    fmt_min,
    fmt_p,
    fmt_p_stars,
    fmt_pct,
    fmt_pct0,
    fmt_r,
    fmt_raw,
    get_render_mode,
    register_formatter,
    set_render_mode,
)


class TestFmtP:
    """Tests for p-value formatting."""

    def test_very_small_p(self):
        result = fmt_p(4.52e-17)
        assert "×10" in result
        assert "⁻¹⁷" in result
        assert result.startswith("4.5")

    def test_small_p_scientific(self):
        result = fmt_p(3.2e-5)
        assert "×10" in result
        assert "⁻⁵" in result

    def test_moderate_p(self):
        assert fmt_p(0.042) == "0.042"

    def test_borderline_p(self):
        assert fmt_p(0.050) == "0.05"

    def test_large_p(self):
        assert fmt_p(0.523) == "0.523"

    def test_p_below_threshold(self):
        result = fmt_p(0.0003)
        assert "×10" in result or "< 0.001" == result

    def test_p_zero(self):
        assert fmt_p(0) == "< 0.001"

    def test_p_one(self):
        assert fmt_p(1.0) == "1"

    def test_p_nan(self):
        assert fmt_p(float("nan")) == "N/A"

    def test_p_none(self):
        assert fmt_p(None) == "N/A"

    def test_p_negative(self):
        assert fmt_p(-0.05) == "N/A"

    def test_p_trailing_zeros_stripped(self):
        # 0.050 should become "0.05", not "0.050"
        result = fmt_p(0.050)
        assert not result.endswith("0") or result == "0"


class TestFmtPStars:
    """Tests for significance stars."""

    def test_three_stars(self):
        assert fmt_p_stars(0.0001) == "***"
        assert fmt_p_stars(0.0009) == "***"

    def test_two_stars(self):
        assert fmt_p_stars(0.001) == "**"
        assert fmt_p_stars(0.005) == "**"

    def test_one_star(self):
        assert fmt_p_stars(0.01) == "*"
        assert fmt_p_stars(0.04) == "*"

    def test_ns(self):
        assert fmt_p_stars(0.05) == "n.s."
        assert fmt_p_stars(0.5) == "n.s."
        assert fmt_p_stars(1.0) == "n.s."

    def test_nan(self):
        assert fmt_p_stars(float("nan")) == "N/A"

    def test_none(self):
        assert fmt_p_stars(None) == "N/A"

    def test_zero(self):
        assert fmt_p_stars(0) == "***"


class TestFmtR:
    """Tests for effect size formatting."""

    def test_negative(self):
        result = fmt_r(-0.456)
        assert result == "−0.46"
        assert "−" in result  # Unicode minus, not hyphen

    def test_positive(self):
        assert fmt_r(0.32) == "+0.32"

    def test_zero(self):
        assert fmt_r(0.0) == "0.00"

    def test_no_sign(self):
        assert fmt_r(0.32, sign=False) == "0.32"

    def test_negative_no_sign(self):
        result = fmt_r(-0.32, sign=False)
        assert "−" in result
        assert "0.32" in result

    def test_nan(self):
        assert fmt_r(float("nan")) == "N/A"

    def test_none(self):
        assert fmt_r(None) == "N/A"

    def test_large_r(self):
        assert fmt_r(1.0) == "+1.00"

    def test_small_r(self):
        result = fmt_r(0.001)
        assert result == "+0.00"


class TestFmtInt:
    """Tests for integer formatting."""

    def test_thousands(self):
        assert fmt_int(1234567) == "1,234,567"

    def test_small(self):
        assert fmt_int(42) == "42"

    def test_float_rounds(self):
        assert fmt_int(42.7) == "43"

    def test_zero(self):
        assert fmt_int(0) == "0"

    def test_negative(self):
        assert fmt_int(-1234) == "-1,234"

    def test_nan(self):
        assert fmt_int(float("nan")) == "N/A"

    def test_none(self):
        assert fmt_int(None) == "N/A"


class TestFmtPct:
    """Tests for percentage formatting."""

    def test_basic(self):
        assert fmt_pct(0.452) == "45.2%"

    def test_one(self):
        assert fmt_pct(1.0) == "100.0%"

    def test_zero(self):
        assert fmt_pct(0.0) == "0.0%"

    def test_over_one(self):
        assert fmt_pct(1.5) == "150.0%"

    def test_nan(self):
        assert fmt_pct(float("nan")) == "N/A"


class TestFmtPct0:
    """Tests for whole-number percentage formatting (:pct0)."""

    def test_rounds_to_whole(self):
        assert fmt_pct0(0.368) == "37%"
        assert fmt_pct0(0.026) == "3%"

    def test_zero_and_one(self):
        assert fmt_pct0(0.0) == "0%"
        assert fmt_pct0(1.0) == "100%"

    def test_nan(self):
        assert fmt_pct0(float("nan")) == "N/A"

    def test_registered(self):
        assert FORMATTERS["pct0"] is fmt_pct0


class TestFmtFloats:
    """Tests for float formatters (f0-f3)."""

    def test_f0(self):
        assert fmt_f0(42.7) == "43"
        assert fmt_f0(float("nan")) == "N/A"

    def test_f1(self):
        assert fmt_f1(42.34) == "42.3"
        assert fmt_f1(None) == "N/A"

    def test_f2(self):
        assert fmt_f2(42.346) == "42.35"  # Rounds
        assert fmt_f2(float("nan")) == "N/A"

    def test_f3(self):
        assert fmt_f3(42.3456) == "42.346"
        assert fmt_f3(None) == "N/A"

    def test_negative(self):
        assert fmt_f2(-3.14) == "-3.14"


class TestFmtTime:
    """Tests for time formatters."""

    def test_minutes(self):
        assert fmt_min(150) == "2.5 min"

    def test_minutes_zero(self):
        assert fmt_min(0) == "0.0 min"

    def test_minutes_nan(self):
        assert fmt_min(float("nan")) == "N/A"

    def test_hours(self):
        assert fmt_hr(5400) == "1.5 hr"

    def test_hours_zero(self):
        assert fmt_hr(0) == "0.0 hr"

    def test_hours_nan(self):
        assert fmt_hr(float("nan")) == "N/A"


class TestFmtRaw:
    """Tests for raw formatter."""

    def test_string(self):
        assert fmt_raw("hello") == "hello"

    def test_number(self):
        assert fmt_raw(42) == "42"

    def test_nan(self):
        assert fmt_raw(float("nan")) == "N/A"

    def test_none(self):
        assert fmt_raw(None) == "N/A"


class TestRegistry:
    """Tests for the formatter registry."""

    def test_all_formatters_registered(self):
        expected = {
            "p",
            "p_stars",
            "stars",
            "r",
            "int",
            "pct",
            "f0",
            "f1",
            "f2",
            "f3",
            "min",
            "hr",
            "raw",
            "fmt0",
            "fmt1",
            "fmt2",
            "fmt3",
            "float0",
            "float1",
            "float2",
            "float3",
        }
        assert expected.issubset(set(FORMATTERS.keys()))

    def test_all_formatters_callable(self):
        for name, func in FORMATTERS.items():
            assert callable(func), f"Formatter '{name}' is not callable"

    def test_register_custom(self):
        # Use a unique name to avoid conflicts
        name = "_test_custom_fmt"
        try:
            FORMATTERS.pop(name, None)  # Clean up if present
            register_formatter(name, lambda x: f"custom:{x}")
            assert FORMATTERS[name](42) == "custom:42"
        finally:
            FORMATTERS.pop(name, None)

    def test_register_duplicate_raises(self):
        with pytest.raises(ValueError, match="already registered"):
            register_formatter("p", lambda x: "nope")

    def test_formatters_handle_nan(self):
        """All formatters should return 'N/A' for NaN."""
        for name, func in FORMATTERS.items():
            if name in ("raw",):
                continue
            result = func(float("nan"))
            assert result == "N/A", f"Formatter '{name}' returned '{result}' for NaN"


class TestFormatterAliases:
    """Tests for formatter aliases."""

    def test_fmt_aliases_exist(self):
        for i in range(4):
            assert f"fmt{i}" in FORMATTERS
            assert f"float{i}" in FORMATTERS

    def test_fmt_aliases_match(self):
        assert FORMATTERS["fmt0"] is FORMATTERS["f0"]
        assert FORMATTERS["fmt1"] is FORMATTERS["f1"]
        assert FORMATTERS["fmt2"] is FORMATTERS["f2"]
        assert FORMATTERS["fmt3"] is FORMATTERS["f3"]

    def test_float_aliases_match(self):
        assert FORMATTERS["float0"] is FORMATTERS["f0"]
        assert FORMATTERS["float1"] is FORMATTERS["f1"]

    def test_aliases_produce_same_output(self):
        assert FORMATTERS["fmt2"](3.14159) == FORMATTERS["f2"](3.14159)


class TestRenderMode:
    """Tests for render mode switching."""

    def setup_method(self):
        """Reset to unicode mode before each test."""
        set_render_mode("unicode")

    def teardown_method(self):
        """Reset to unicode mode after each test."""
        set_render_mode("unicode")

    def test_default_mode_is_unicode(self):
        assert get_render_mode() == "unicode"

    def test_set_latex_mode(self):
        set_render_mode("latex")
        assert get_render_mode() == "latex"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown render mode"):
            set_render_mode("html")

    def test_fmt_p_unicode_mode(self):
        set_render_mode("unicode")
        result = fmt_p(3.8e-4)
        assert "×10" in result
        assert "⁻⁴" in result

    def test_fmt_p_latex_mode(self):
        set_render_mode("latex")
        result = fmt_p(3.8e-4)
        assert "\\times" in result
        assert "10^{" in result
        # No $...$ wrapping — template controls math delimiters
        assert not result.startswith("$")
        assert not result.endswith("$")

    def test_fmt_p_latex_moderate_p_unchanged(self):
        """Moderate p-values (>= 0.001) are not affected by render mode."""
        set_render_mode("latex")
        assert fmt_p(0.042) == "0.042"

    def test_fmt_r_unicode_mode(self):
        set_render_mode("unicode")
        result = fmt_r(-0.45)
        assert "−" in result  # Unicode minus
        assert result == "−0.45"

    def test_fmt_r_latex_mode(self):
        set_render_mode("latex")
        result = fmt_r(-0.45)
        # ASCII minus, no $...$ wrapping
        assert result == "-0.45"

    def test_fmt_r_latex_positive_with_sign(self):
        set_render_mode("latex")
        result = fmt_r(0.32, sign=True)
        assert result == "+0.32"

    def test_fmt_r_latex_positive_no_sign(self):
        set_render_mode("latex")
        result = fmt_r(0.32, sign=False)
        assert result == "0.32"

    def test_fmt_r_latex_in_math_context(self):
        """Verify that LaTeX mode output works naturally in $...$ context."""
        set_render_mode("latex")
        # Simulating what the template does: $r = {{x:r}}$
        r_val = fmt_r(-0.45)
        rendered = f"$r = {r_val}$"
        assert rendered == "$r = -0.45$"  # Clean, no double $

    def test_fmt_p_latex_in_math_context(self):
        """Verify small p-value in $...$ context."""
        set_render_mode("latex")
        p_val = fmt_p(3.8e-4)
        rendered = f"$p = {p_val}$"
        assert "$$" not in rendered  # No nested delimiters


# --- per-project numeric house style ----------------------------------------
#
# Defaults must reproduce the historical output exactly; a project opts in via a
# `formatting:` section. The cases below are the ones a migration actually turns on.

import pytest  # noqa: E402

from paper_forge.formatters import (  # noqa: E402
    FormatterConfig,
    set_formatter_config,
    set_render_mode,
)


class TestFormatterConfigDefaults:
    """With no configuration, nothing about the output changes."""

    def test_r_defaults_to_two_decimals(self):
        assert fmt_r(0.029) == "+0.03"

    def test_p_small_band_default_loses_a_sig_fig(self):
        # Documents the default behaviour the opt-in exists to change.
        assert fmt_p(0.0062) == "0.006"

    def test_p_small_band_default_rounds_out_of_band(self):
        assert fmt_p(0.0096) == "0.01"

    def test_p_zero_defaults_to_lt_0001(self):
        assert fmt_p(0.0) == "< 0.001"


class TestEffectSizePrecision:
    def test_three_decimals_preserves_the_distinction(self):
        # The paper's argument separates these two effects; at 2dp both are "+0.03".
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(0.029) == "+0.029"
        assert fmt_r(0.035) == "+0.035"

    def test_three_decimals_does_not_cross_the_interpretation_threshold(self):
        # At 2dp 0.096 renders "+0.10", reading as if it crossed the 0.1 branch point.
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(0.096) == "+0.096"

    def test_negative_keeps_unicode_minus(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(-0.520) == "−0.520"

    def test_zero_honours_configured_precision(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(0.0) == "0.000"

    def test_negative_zero_gets_no_sign(self):
        # IEEE -0.0 < 0 is False, so no spurious minus.
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(-0.0) == "0.000"

    def test_missing_ignores_config(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(None) == "N/A"

    def test_latex_mode_respects_precision(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        set_render_mode("latex")
        assert fmt_r(-0.029) == "-0.029"

    def test_f3_is_independent_of_r_decimals(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert FORMATTERS["f3"](0.029) == "0.029"


class TestPValueSignificantFigures:
    def test_keeps_two_sig_figs_in_the_small_band(self):
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.0062) == "0.0062"

    def test_does_not_round_out_of_the_band(self):
        # The critical case: the default path renders this as "0.01".
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.0096) == "0.0096"

    def test_upper_edge_of_band(self):
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.0099) == "0.0099"

    def test_value_that_genuinely_rounds_to_the_boundary(self):
        # 0.00999 at 2 sig figs really is 0.01; rounding is not avoidable.
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.00999) == "0.01"

    def test_not_applied_above_the_band(self):
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.042) == "0.042"

    def test_lower_edge_of_band(self):
        set_formatter_config(FormatterConfig(p_small_sig_figs=2))
        assert fmt_p(0.001) == "0.001"


class TestPValueClamp:
    def test_below_threshold_is_clamped(self):
        set_formatter_config(FormatterConfig(p_clamp_exp=300))
        assert fmt_p(1e-301) == "< 10⁻³⁰⁰"

    def test_exactly_at_threshold_is_not_clamped(self):
        # Strict less-than: 1e-300 still carries information.
        set_formatter_config(FormatterConfig(p_clamp_exp=300))
        assert fmt_p(1e-300) != "< 10⁻³⁰⁰"

    def test_zero_is_clamped_when_a_clamp_is_configured(self):
        # 0 is below any positive threshold; it must not fall through to "< 0.001".
        set_formatter_config(FormatterConfig(p_clamp_exp=300))
        assert fmt_p(0.0) == "< 10⁻³⁰⁰"

    def test_latex_clamp(self):
        set_formatter_config(FormatterConfig(p_clamp_exp=300))
        set_render_mode("latex")
        assert fmt_p(1e-301) == "< 10^{-300}"

    def test_ordinary_small_p_still_scientific(self):
        set_formatter_config(FormatterConfig(p_clamp_exp=300))
        assert fmt_p(4.52e-17) == "4.5×10⁻¹⁷"


class TestFormatterConfigValidation:
    @pytest.mark.parametrize("bad", [0, 1, 2, 301])
    def test_rejects_clamp_exponents_that_would_swallow_real_p_values(self, bad):
        # p_clamp_exp=1 means a 0.1 threshold — it would clamp a typical alpha.
        with pytest.raises(ValueError, match="p_clamp_exp"):
            set_formatter_config(FormatterConfig(p_clamp_exp=bad))

    def test_rejects_absurd_r_decimals(self):
        with pytest.raises(ValueError, match="r_decimals"):
            set_formatter_config(FormatterConfig(r_decimals=-1))

    def test_rejects_absurd_sig_figs(self):
        with pytest.raises(ValueError, match="p_small_sig_figs"):
            set_formatter_config(FormatterConfig(p_small_sig_figs=0))

    def test_config_is_frozen(self):
        # A held reference must not be mutable behind the setter's back.
        from dataclasses import FrozenInstanceError

        cfg = FormatterConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.r_decimals = 5


class TestFormatterStateIsolation:
    """The autouse fixture must reset the house style between tests."""

    def test_a_sets_three_decimals(self):
        set_formatter_config(FormatterConfig(r_decimals=3))
        assert fmt_r(0.029) == "+0.029"

    def test_b_sees_the_default_again(self):
        assert fmt_r(0.029) == "+0.03"
