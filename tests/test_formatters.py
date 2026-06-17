"""Tests for the formatters module."""

from __future__ import annotations

import math

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
        expected = {"p", "p_stars", "stars", "r", "int", "pct",
                    "f0", "f1", "f2", "f3", "min", "hr", "raw",
                    "fmt0", "fmt1", "fmt2", "fmt3",
                    "float0", "float1", "float2", "float3"}
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
        assert result.startswith("$")
        assert result.endswith("$")

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
        assert result == "$-0.45$"

    def test_fmt_r_latex_positive_with_sign(self):
        set_render_mode("latex")
        result = fmt_r(0.32, sign=True)
        assert result == "$+0.32$"

    def test_fmt_r_latex_positive_no_sign(self):
        set_render_mode("latex")
        result = fmt_r(0.32, sign=False)
        assert result == "$0.32$"

