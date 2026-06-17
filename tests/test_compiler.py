"""Tests for the compiler module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_forge.compiler import (
    _flatten_dict,
    compile_manuscript,
    load_all_results,
    load_project_config,
    resolve_placeholder,
)
from paper_forge.formatters import FORMATTERS


@pytest.fixture
def results_dir(tmp_path: Path) -> Path:
    """Create a temporary results directory with sample JSON files."""
    rdir = tmp_path / "results"
    rdir.mkdir()

    # Create analysis results
    analysis = {
        "unit_name": "analysis",
        "results": {
            "n_samples": 150,
            "p_value": 0.003,
            "effect_size": -0.42,
            "mean_duration": 123.4,
        },
        "provenance": {"git_commit": "abc1234"},
    }
    (rdir / "analysis.json").write_text(json.dumps(analysis))

    # Create demographics results
    demographics = {
        "unit_name": "demographics",
        "results": {
            "n_participants": 50,
            "age_mean": 25.3,
            "pct_female": 0.56,
        },
        "provenance": {"git_commit": "abc1234"},
    }
    (rdir / "demographics.json").write_text(json.dumps(demographics))

    return rdir


@pytest.fixture
def project_dir(tmp_path: Path, results_dir: Path) -> Path:
    """Create a complete project directory for testing."""
    import shutil

    # Copy results
    project_results = tmp_path / "results"
    if not project_results.exists():
        shutil.copytree(results_dir, project_results)

    # Create manuscript template
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "We analyzed {{stats.n_samples:int}} samples.\n"
        "The effect was {{stats.effect_size:r}} (p = {{stats.p_value:p}}).\n"
        "We had {{demo.n_participants:int}} participants.\n"
    )

    # Create project config
    config = {
        "manuscript": "manuscript.md",
        "output": "compiled.md",
        "results_dir": "results/",
        "prefix_map": {
            "analysis": "stats",
            "demographics": "demo",
        },
    }
    import yaml

    (tmp_path / "project.yaml").write_text(yaml.dump(config))

    return tmp_path


class TestFlattenDict:
    """Tests for the _flatten_dict helper."""

    def test_simple(self):
        out: dict = {}
        _flatten_dict({"a": 1, "b": 2}, "prefix", out)
        assert out == {"prefix.a": 1, "prefix.b": 2}

    def test_nested(self):
        out: dict = {}
        _flatten_dict({"a": {"b": 1, "c": 2}}, "p", out)
        assert out == {"p.a.b": 1, "p.a.c": 2}

    def test_empty(self):
        out: dict = {}
        _flatten_dict({}, "p", out)
        assert out == {}


class TestLoadProjectConfig:
    """Tests for loading project configuration."""

    def test_valid_config(self, project_dir: Path):
        config = load_project_config(project_dir / "project.yaml")
        assert config["manuscript"] == "manuscript.md"
        assert config["output"] == "compiled.md"
        assert config["results_dir"] == "results/"

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path / "nonexistent.yaml")

    def test_missing_required_fields(self, tmp_path: Path):
        import yaml

        config_path = tmp_path / "bad.yaml"
        config_path.write_text(yaml.dump({"manuscript": "ms.md"}))
        with pytest.raises(ValueError, match="missing required"):
            load_project_config(config_path)


class TestLoadAllResults:
    """Tests for loading and flattening results."""

    def test_without_prefix_map(self, results_dir: Path):
        flat = load_all_results(results_dir)
        assert "analysis.n_samples" in flat
        assert flat["analysis.n_samples"] == 150
        assert "demographics.n_participants" in flat
        assert flat["demographics.n_participants"] == 50

    def test_with_prefix_map(self, results_dir: Path):
        prefix_map = {"analysis": "stats", "demographics": "demo"}
        flat = load_all_results(results_dir, prefix_map)
        assert "stats.n_samples" in flat
        assert flat["stats.n_samples"] == 150
        assert "demo.n_participants" in flat
        assert flat["demo.n_participants"] == 50

    def test_missing_dir(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_all_results(tmp_path / "nonexistent")


class TestResolvePlaceholder:
    """Tests for placeholder resolution."""

    def test_simple_key(self):
        results = {"stats.p": 0.003}
        assert resolve_placeholder("stats.p", results) == "0.003"

    def test_with_formatter(self):
        results = {"stats.p": 0.003}
        result = resolve_placeholder("stats.p:p", results)
        assert result == "0.003"

    def test_int_formatter(self):
        results = {"stats.n": 1234}
        assert resolve_placeholder("stats.n:int", results) == "1,234"

    def test_r_formatter(self):
        results = {"stats.r": -0.42}
        result = resolve_placeholder("stats.r:r", results)
        assert "−" in result
        assert "0.42" in result

    def test_missing_key(self):
        results = {"stats.p": 0.003}
        with pytest.raises(KeyError, match="not found"):
            resolve_placeholder("stats.missing", results)

    def test_unknown_formatter(self):
        results = {"stats.p": 0.003}
        with pytest.raises(KeyError, match="Unknown formatter"):
            resolve_placeholder("stats.p:nonexistent", results)

    def test_stars_formatter(self):
        results = {"stats.p": 0.0001}
        assert resolve_placeholder("stats.p:stars", results) == "***"

    def test_pct_formatter(self):
        results = {"stats.frac": 0.45}
        assert resolve_placeholder("stats.frac:pct", results) == "45.0%"


class TestCompileManuscript:
    """Tests for the full compilation pipeline."""

    def test_basic_compilation(self, project_dir: Path):
        result = compile_manuscript(project_dir / "project.yaml")
        assert "150" in result
        assert "−0.42" in result
        assert "0.003" in result
        assert "50" in result
        # Should not contain any unresolved placeholders
        assert "{{" not in result

    def test_output_file_written(self, project_dir: Path):
        compile_manuscript(project_dir / "project.yaml")
        output = project_dir / "compiled.md"
        assert output.exists()
        content = output.read_text()
        assert "{{" not in content

    def test_check_only_does_not_write(self, project_dir: Path):
        compile_manuscript(project_dir / "project.yaml", check_only=True)
        output = project_dir / "compiled.md"
        assert not output.exists()

    def test_missing_config(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            compile_manuscript(tmp_path / "nonexistent.yaml")

    def test_derived_keys(self, project_dir: Path):
        import yaml

        # Update config with derived key (literal expression since dot-keys
        # can't be Python identifiers)
        config_path = project_dir / "project.yaml"
        config = yaml.safe_load(config_path.read_text())
        config["derived"] = {
            "computed.ratio": "42.0 / 2"
        }

        # Update manuscript to use derived key
        manuscript = project_dir / "manuscript.md"
        content = manuscript.read_text()
        content += "\nDerived: {{computed.ratio:f1}}\n"
        manuscript.write_text(content)
        config_path.write_text(yaml.dump(config))

        result = compile_manuscript(config_path)
        assert "21.0" in result


class TestRenderModeAutoDetect:
    """Test that compile_manuscript auto-detects render mode from config."""

    def test_latex_mode_from_pandoc_args(self, project_dir: Path) -> None:
        """Config with --pdf-engine=xelatex should trigger latex mode."""
        import yaml
        from paper_forge.formatters import get_render_mode, set_render_mode

        # Reset to unicode first
        set_render_mode("unicode")

        config_path = project_dir / "project.yaml"
        config = yaml.safe_load(config_path.read_text())
        config["rendering"] = {
            "engine": "pandoc",
            "pandoc_args": ["--pdf-engine=xelatex"],
        }
        config_path.write_text(yaml.dump(config))

        compile_manuscript(config_path)
        assert get_render_mode() == "latex"

        # Clean up
        set_render_mode("unicode")

    def test_unicode_mode_when_no_latex_engine(self, project_dir: Path) -> None:
        """Config without a LaTeX engine should keep unicode mode."""
        from paper_forge.formatters import get_render_mode, set_render_mode

        set_render_mode("unicode")

        config_path = project_dir / "project.yaml"
        compile_manuscript(config_path)
        assert get_render_mode() == "unicode"

