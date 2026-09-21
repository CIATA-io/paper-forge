"""Formatters for scientific values in manuscripts.

Each formatter takes a numeric value and returns a human-readable string
suitable for inclusion in a scientific manuscript. All formatters handle
NaN and None gracefully, returning "N/A".

Formatters are registered in the global FORMATTERS dict and can be referenced
by short name in manuscript placeholders, e.g. ``{{stats.p_value:p}}``.

Render Modes
~~~~~~~~~~~~

Formatters support two render modes:

- ``"unicode"`` (default): Uses Unicode superscripts and minus signs.
  Best for plain text and HTML output.
- ``"latex"``: Produces LaTeX math expressions (e.g. ``$3.8 \\times 10^{-4}$``).
  Required when rendering to PDF via XeLaTeX/pdfLaTeX.

Set the mode with :func:`set_render_mode` or let the compiler auto-detect
from ``project.yaml``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

# Unicode characters for formatting
_SUPERSCRIPT_DIGITS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_UNICODE_MINUS = "\u2212"  # −

# ---------------------------------------------------------------------------
# Render mode
# ---------------------------------------------------------------------------

_RENDER_MODE: str = "unicode"  # "unicode" or "latex"


@dataclass(frozen=True)
class FormatterConfig:
    """A project's numeric house style.

    A paper already has conventions for how it prints numbers, and a migration must not
    change them: wiring a number should change *where it comes from*, never *what it
    says*. These are the knobs where paper-forge's defaults are not universal.

    Every default reproduces the historical output exactly, so a project without a
    ``formatting:`` section is byte-for-byte unaffected.

    Attributes:
        r_decimals: Decimal places for ``:r``. Two is enough for most papers; a paper
            whose argument turns on small effects needs three — at two decimals
            r = 0.029 and r = 0.035 both print "+0.03", erasing the distinction.
        p_small_sig_figs: Significant figures for p in [0.001, 0.01). ``None`` keeps the
            default 3-decimal path. Expressed as significant figures rather than decimals
            because decimals fail in this band: 3 gives "0.006" for 0.0062 (one sig fig)
            and "0.01" for 0.0096, which rounds out of the band and reads as p ≥ 0.01.
        p_clamp_exp: Print ``< 10⁻ᴺ`` for p below ``10**-N`` instead of a mantissa whose
            digits are below the float64 denormal floor and carry no information.
            ``None`` disables clamping.
    """

    r_decimals: int = 2
    p_small_sig_figs: int | None = None
    p_clamp_exp: int | None = None


_FMT_CONFIG: FormatterConfig = FormatterConfig()


def set_formatter_config(config: FormatterConfig) -> None:
    """Install the project's numeric house style.

    Mirrors :func:`set_render_mode`: module-global state read by the formatters at call
    time, set once per compile. Frozen config, so a caller holding a reference cannot
    mutate it behind the setter's back.

    Raises:
        ValueError: If a knob is outside its sensible range. ``p_clamp_exp`` below 3 is
            rejected because a threshold of 10⁻¹ or larger would clamp ordinary
            p-values — including a typical alpha — into "< 10⁻¹".
    """
    if config.r_decimals < 0 or config.r_decimals > 10:
        raise ValueError(f"r_decimals must be in [0, 10], got {config.r_decimals}")
    if config.p_small_sig_figs is not None and not (1 <= config.p_small_sig_figs <= 10):
        raise ValueError(
            f"p_small_sig_figs must be in [1, 10], got {config.p_small_sig_figs}"
        )
    if config.p_clamp_exp is not None and not (3 <= config.p_clamp_exp <= 300):
        raise ValueError(f"p_clamp_exp must be in [3, 300], got {config.p_clamp_exp}")
    global _FMT_CONFIG
    _FMT_CONFIG = config


def get_formatter_config() -> FormatterConfig:
    """The numeric house style currently in force."""
    return _FMT_CONFIG


def set_render_mode(mode: str) -> None:
    """Set the global render mode for formatters.

    Args:
        mode: Either ``"unicode"`` or ``"latex"``.

    Raises:
        ValueError: If mode is not recognized.
    """
    global _RENDER_MODE
    if mode not in ("unicode", "latex"):
        raise ValueError(f"Unknown render mode '{mode}'. Use 'unicode' or 'latex'.")
    _RENDER_MODE = mode


def get_render_mode() -> str:
    """Return the current render mode (``'unicode'`` or ``'latex'``)."""
    return _RENDER_MODE


def _is_missing(x: object) -> bool:
    """Check if a value is None or NaN."""
    if x is None:
        return True
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return False


def fmt_p(p: float | None) -> str:
    """Format a p-value for manuscript display.

    Uses scientific notation for very small values. The output format depends
    on the render mode:

    - ``"unicode"``: ``'4.5×10⁻¹⁷'`` (Unicode superscripts)
    - ``"latex"``: ``'4.5 \\times 10^{-17}'`` (LaTeX notation, no ``$`` delimiters)

    In LaTeX mode the output does **not** include ``$...$`` delimiters so
    that template authors can wrap placeholders in math mode naturally::

        $p = {{stats.p_value:p}}$   →   $p = 3.8 \times 10^{-4}$

    Args:
        p: The p-value to format.

    Returns:
        Formatted string.

    Examples:
        >>> fmt_p(4.52e-17)
        '4.5×10⁻¹⁷'
        >>> fmt_p(0.042)
        '0.042'
        >>> fmt_p(0.0003)
        '3.0×10⁻⁴'
        >>> fmt_p(0.0)
        '< 0.001'
    """
    if _is_missing(p):
        return "N/A"
    p = float(p)
    if p < 0:
        return "N/A"
    if p >= 0.001:
        # In [0.001, 0.01) three decimals can cost a significant figure (0.0062 -> 0.006)
        # or round out of the band (0.0096 -> 0.01, which reads as p >= 0.01), so a
        # project may ask for significant figures here instead.
        if _FMT_CONFIG.p_small_sig_figs is not None and p < 0.01:
            return f"{p:.{_FMT_CONFIG.p_small_sig_figs}g}"
        # Use up to 3 significant figures, but strip trailing zeros
        return f"{p:.3f}".rstrip("0").rstrip(".")
    # The clamp is checked before the p == 0 case on purpose: 0 is below any positive
    # threshold, so a configured clamp should catch it rather than falling through to
    # "< 0.001", which would understate a value stored as exactly zero.
    clamp_exp = _FMT_CONFIG.p_clamp_exp
    if clamp_exp is not None and p < 10.0**-clamp_exp:
        if _RENDER_MODE == "latex":
            return f"< 10^{{-{clamp_exp}}}"
        return f"< 10{str(-clamp_exp).translate(_SUPERSCRIPT_DIGITS)}"
    # Reached only when no clamp is configured; also guards log10(0) below.
    if p == 0:
        return "< 0.001"
    # Scientific notation
    exp = math.floor(math.log10(abs(p)))
    mantissa = p / (10**exp)
    if _RENDER_MODE == "latex":
        return f"{mantissa:.1f} \\times 10^{{{exp}}}"
    exp_str = str(exp).translate(_SUPERSCRIPT_DIGITS)
    return f"{mantissa:.1f}×10{exp_str}"


def fmt_p_stars(p: float | None) -> str:
    """Format a p-value as significance stars.

    Args:
        p: The p-value.

    Returns:
        ``'***'`` for p < 0.001, ``'**'`` for p < 0.01,
        ``'*'`` for p < 0.05, ``'n.s.'`` otherwise.

    Examples:
        >>> fmt_p_stars(0.0001)
        '***'
        >>> fmt_p_stars(0.03)
        '*'
        >>> fmt_p_stars(0.12)
        'n.s.'
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


def fmt_r(r: float | None, sign: bool = True) -> str:
    """Format an effect size (correlation coefficient).

    Uses Unicode minus sign for negative values and rounds to 2 decimal places.
    In ``"latex"`` render mode, uses ASCII minus (no ``$`` delimiters) so
    that template authors can wrap placeholders in math mode naturally::

        $r = {{stats.corr:r}}$   →   $r = -0.45$

    Args:
        r: The effect size / correlation coefficient.
        sign: If True, include a sign prefix (``+`` or ``−``) for non-zero values.

    Returns:
        Formatted string, e.g. ``'−0.45'``, ``'+0.32'``, ``'0.00'``.

    .. warning::

        When ``sign=True`` (the default), the formatter adds a ``+`` prefix
        for positive values. If your template already includes a sign character
        (e.g. ``$r = +{{stats.r:r}}$``), you'll get a double sign like ``++0.32``.
        Either omit the sign from the template or use ``:r`` without a
        prefix sign in the surrounding text.

    Examples:
        >>> fmt_r(-0.456)
        '−0.46'
        >>> fmt_r(0.32)
        '+0.32'
        >>> fmt_r(0.32, sign=False)
        '0.32'
    """
    if _is_missing(r):
        return "N/A"
    r = float(r)
    decimals = _FMT_CONFIG.r_decimals
    abs_val = f"{abs(r):.{decimals}f}"
    # The zero case must honour the configured precision too, or a 3-decimal paper
    # prints "0.00" for exactly zero and "0.029" everywhere else.
    zero_val = f"{0.0:.{decimals}f}"
    if _RENDER_MODE == "latex":
        # Use ASCII minus, no $...$ — template controls math delimiters
        if not sign:
            if r < 0:
                return f"-{abs_val}"
            return abs_val
        if r < 0:
            return f"-{abs_val}"
        if r > 0:
            return f"+{abs_val}"
        return zero_val
    if not sign:
        if r < 0:
            return f"{_UNICODE_MINUS}{abs_val}"
        return abs_val
    if r < 0:
        return f"{_UNICODE_MINUS}{abs_val}"
    if r > 0:
        return f"+{abs_val}"
    return zero_val


def fmt_int(n: float | int | None) -> str:
    """Format an integer with thousands separator.

    Args:
        n: The number to format (will be rounded to int).

    Returns:
        Formatted string with comma thousands separator, e.g. ``'1,234'``.

    Examples:
        >>> fmt_int(1234567)
        '1,234,567'
        >>> fmt_int(42.7)
        '43'
    """
    if _is_missing(n):
        return "N/A"
    return f"{round(float(n)):,}"


def fmt_pct(frac: float | None) -> str:
    """Format a fraction as a percentage.

    Args:
        frac: The fraction (0–1 range) to convert to percentage.

    Returns:
        Formatted percentage string, e.g. ``'45.2%'``.

    Examples:
        >>> fmt_pct(0.452)
        '45.2%'
        >>> fmt_pct(1.0)
        '100.0%'
    """
    if _is_missing(frac):
        return "N/A"
    return f"{float(frac) * 100:.1f}%"


def fmt_pct0(frac: float | None) -> str:
    """Format a fraction as a whole-number percentage (no decimals).

    Args:
        frac: The fraction (0–1 range) to convert to percentage.

    Returns:
        Formatted percentage string rounded to the nearest integer, e.g. ``'37%'``.

    Examples:
        >>> fmt_pct0(0.368)
        '37%'
        >>> fmt_pct0(0.026)
        '3%'
    """
    if _is_missing(frac):
        return "N/A"
    return f"{float(frac) * 100:.0f}%"


def fmt_f0(x: float | None) -> str:
    """Format a float with 0 decimal places.

    Args:
        x: The number to format.

    Returns:
        Formatted string, e.g. ``'42'``.
    """
    if _is_missing(x):
        return "N/A"
    return f"{float(x):.0f}"


def fmt_f1(x: float | None) -> str:
    """Format a float with 1 decimal place.

    Args:
        x: The number to format.

    Returns:
        Formatted string, e.g. ``'42.3'``.
    """
    if _is_missing(x):
        return "N/A"
    return f"{float(x):.1f}"


def fmt_f2(x: float | None) -> str:
    """Format a float with 2 decimal places.

    Args:
        x: The number to format.

    Returns:
        Formatted string, e.g. ``'42.31'``.
    """
    if _is_missing(x):
        return "N/A"
    return f"{float(x):.2f}"


def fmt_f3(x: float | None) -> str:
    """Format a float with 3 decimal places.

    Args:
        x: The number to format.

    Returns:
        Formatted string, e.g. ``'42.314'``.
    """
    if _is_missing(x):
        return "N/A"
    return f"{float(x):.3f}"


def fmt_min(seconds: float | None) -> str:
    """Format seconds as minutes with 1 decimal place.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string, e.g. ``'2.5 min'``.

    Examples:
        >>> fmt_min(150)
        '2.5 min'
    """
    if _is_missing(seconds):
        return "N/A"
    return f"{float(seconds) / 60:.1f} min"


def fmt_hr(seconds: float | None) -> str:
    """Format seconds as hours with 1 decimal place.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string, e.g. ``'1.5 hr'``.

    Examples:
        >>> fmt_hr(5400)
        '1.5 hr'
    """
    if _is_missing(seconds):
        return "N/A"
    return f"{float(seconds) / 3600:.1f} hr"


def fmt_raw(x: object) -> str:
    """Return the value as-is (string conversion only).

    This is the default formatter used when no formatter is specified
    in a placeholder.

    Args:
        x: Any value.

    Returns:
        String representation of the value.
    """
    if _is_missing(x):
        return "N/A"
    return str(x)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

FORMATTERS: dict[str, Callable] = {
    "p": fmt_p,
    "p_stars": fmt_p_stars,
    "stars": fmt_p_stars,
    "r": fmt_r,
    "int": fmt_int,
    "pct": fmt_pct,
    "pct0": fmt_pct0,
    "f0": fmt_f0,
    "f1": fmt_f1,
    "f2": fmt_f2,
    "f3": fmt_f3,
    "min": fmt_min,
    "hr": fmt_hr,
    "raw": fmt_raw,
    # Aliases — common alternative names
    "fmt0": fmt_f0,
    "fmt1": fmt_f1,
    "fmt2": fmt_f2,
    "fmt3": fmt_f3,
    "float0": fmt_f0,
    "float1": fmt_f1,
    "float2": fmt_f2,
    "float3": fmt_f3,
}


def register_formatter(name: str, func: Callable) -> None:
    """Register a custom formatter function.

    The function should accept a single numeric argument and return a string.
    It will be available in manuscript placeholders as ``{{key:name}}``.

    Args:
        name: Short name to use in placeholders.
        func: Callable that takes a value and returns a formatted string.

    Raises:
        ValueError: If a formatter with this name is already registered.

    Examples:
        >>> register_formatter("my_fmt", lambda x: f"value={x}")
        >>> FORMATTERS["my_fmt"](42)
        'value=42'
    """
    if name in FORMATTERS:
        raise ValueError(
            f"Formatter '{name}' is already registered. "
            f"Use FORMATTERS['{name}'] = func to override explicitly."
        )
    FORMATTERS[name] = func
