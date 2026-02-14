import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from gdscript_code_graph.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Stdout output tests
# ---------------------------------------------------------------------------


class TestStdoutOutput:
    def test_analyze_exits_zero(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        assert result.exit_code == 0

    def test_analyze_outputs_valid_json(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_analyze_output_has_schema_version(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        parsed = json.loads(result.output)
        assert "schema_version" in parsed
        assert parsed["schema_version"] == "1.0"

    def test_analyze_output_has_nodes(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        parsed = json.loads(result.output)
        assert "nodes" in parsed
        assert len(parsed["nodes"]) == 7

    def test_analyze_output_has_links(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        parsed = json.loads(result.output)
        assert "links" in parsed
        assert len(parsed["links"]) == 7


# ---------------------------------------------------------------------------
# File output tests
# ---------------------------------------------------------------------------


class TestFileOutput:
    def test_file_output_exits_zero(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "out.json"
        result = runner.invoke(
            main, ["analyze", str(fixtures_dir), "--out", str(out_file)]
        )
        assert result.exit_code == 0

    def test_file_output_creates_file(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "out.json"
        runner.invoke(
            main, ["analyze", str(fixtures_dir), "--out", str(out_file)]
        )
        assert out_file.exists()

    def test_file_output_contains_valid_json(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "out.json"
        runner.invoke(
            main, ["analyze", str(fixtures_dir), "--out", str(out_file)]
        )
        parsed = json.loads(out_file.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    def test_file_output_has_expected_keys(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "out.json"
        runner.invoke(
            main, ["analyze", str(fixtures_dir), "--out", str(out_file)]
        )
        parsed = json.loads(out_file.read_text(encoding="utf-8"))
        assert set(parsed.keys()) == {
            "schema_version",
            "meta",
            "nodes",
            "links",
        }

    def test_file_output_short_flag(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        out_file = tmp_path / "out.json"
        result = runner.invoke(
            main, ["analyze", str(fixtures_dir), "-o", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()

    def test_file_output_creates_parent_dirs(
        self, runner: CliRunner, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        """--out should create parent directories if they don't exist."""
        out_file = tmp_path / "nested" / "dir" / "out.json"
        result = runner.invoke(
            main, ["analyze", str(fixtures_dir), "--out", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()


# ---------------------------------------------------------------------------
# Repo name tests
# ---------------------------------------------------------------------------


class TestRepoName:
    def test_repo_name_defaults_to_directory_name(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(fixtures_dir)])
        parsed = json.loads(result.output)
        assert parsed["meta"]["repo"] == "fixtures"

    def test_repo_name_override(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        result = runner.invoke(
            main,
            ["analyze", str(fixtures_dir), "--repo-name", "my-game"],
        )
        parsed = json.loads(result.output)
        assert parsed["meta"]["repo"] == "my-game"


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestExcludeOption:
    def test_exclude_reduces_node_count(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        """--exclude actors should drop character, player, enemy (3 nodes)."""
        result = runner.invoke(
            main,
            ["analyze", str(fixtures_dir), "--exclude", "actors"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        # 7 total - 3 actors = 4 nodes
        assert len(parsed["nodes"]) == 4

    def test_exclude_multiple_dirs(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        """Multiple --exclude flags should all be applied."""
        result = runner.invoke(
            main,
            [
                "analyze", str(fixtures_dir),
                "--exclude", "actors",
                "--exclude", "weapons",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        node_ids = {n["id"] for n in parsed["nodes"]}
        assert "res://actors/player.gd" not in node_ids
        assert "res://weapons/bullet.gd" not in node_ids
        assert "res://utils/helpers.gd" in node_ids

    def test_exclude_short_flag(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        """-e should work as shorthand for --exclude."""
        result = runner.invoke(
            main,
            ["analyze", str(fixtures_dir), "-e", "actors"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        node_ids = {n["id"] for n in parsed["nodes"]}
        assert "res://actors/player.gd" not in node_ids

    def test_exclude_nonexistent_dir_is_harmless(
        self, runner: CliRunner, fixtures_dir: Path
    ) -> None:
        """Excluding a directory that doesn't exist should not error."""
        result = runner.invoke(
            main,
            ["analyze", str(fixtures_dir), "--exclude", "nonexistent"],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed["nodes"]) == 7


class TestErrorHandling:
    def test_missing_project_godot_exits_1(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert result.exit_code == 1

    def test_missing_project_godot_shows_message(
        self, tmp_path: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(tmp_path)])
        assert "project.godot" in result.stderr

    def test_nonexistent_directory_exits_2(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(main, ["analyze", "/nonexistent/path/"])
        assert result.exit_code == 2

    def test_nonexistent_directory_shows_error(
        self, runner: CliRunner
    ) -> None:
        result = runner.invoke(main, ["analyze", "/nonexistent/path/"])
        assert "does not exist" in result.output
