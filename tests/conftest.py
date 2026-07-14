"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from paper_forge.formatters import set_render_mode


@pytest.fixture(autouse=True)
def _reset_render_mode() -> None:
    """Isolate the global formatter render mode across tests.

    ``compile_manuscript`` sets the module-global render mode from the project's
    pdf engine and does not restore it, so without this a test that compiles a
    LaTeX-configured project (e.g. the CLI smoke tests) would leak ``latex`` mode
    into later tests and flip ``fmt_r``'s minus sign.
    """
    set_render_mode("unicode")
    yield
    set_render_mode("unicode")
