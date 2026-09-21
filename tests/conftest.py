"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from paper_forge.formatters import FormatterConfig, set_formatter_config, set_render_mode


@pytest.fixture(autouse=True)
def _reset_formatter_state() -> None:
    """Isolate the global formatter state across tests.

    ``compile_manuscript`` sets the module-global render mode from the project's
    pdf engine, and the numeric house style from its ``formatting:`` section, and
    restores neither. Without this, a test that compiles a LaTeX-configured project
    (e.g. the CLI smoke tests) would leak ``latex`` mode into later tests and flip
    ``fmt_r``'s minus sign; likewise a project configured for three-decimal effect
    sizes would silently change what every later test's ``:r`` renders.
    """
    set_render_mode("unicode")
    set_formatter_config(FormatterConfig())
    yield
    set_render_mode("unicode")
    set_formatter_config(FormatterConfig())
