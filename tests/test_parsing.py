import logging
from pathlib import Path

import pytest
from lark import Tree

from gdscript_code_graph.discovery import ProjectFiles
from gdscript_code_graph.parsing import ParseResult, parse_file, parse_all


class TestParseFile:
    def test_valid_file_returns_tree(self, fixture_project: ProjectFiles) -> None:
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert result.tree is not None
        assert isinstance(result.tree, Tree)
        assert result.error is None

    def test_valid_file_has_source(self, fixture_project: ProjectFiles) -> None:
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert len(result.source) > 0
        assert "extends Character" in result.source

    def test_valid_file_has_correct_res_path(self, fixture_project: ProjectFiles) -> None:
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert result.res_path == "res://actors/player.gd"

    def test_valid_file_has_correct_file_path(self, fixture_project: ProjectFiles) -> None:
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert result.file_path == player_path

    def test_parse_error_file_returns_none_tree(self, fixture_project: ProjectFiles) -> None:
        error_path = next(p for p in fixture_project.gd_files if p.name == "parse_error.gd")
        result = parse_file(error_path, fixture_project.to_res_path(error_path))

        assert result.tree is None
        assert result.error is not None
        assert len(result.error) > 0

    def test_parse_error_file_has_source(self, fixture_project: ProjectFiles) -> None:
        error_path = next(p for p in fixture_project.gd_files if p.name == "parse_error.gd")
        result = parse_file(error_path, fixture_project.to_res_path(error_path))

        assert len(result.source) > 0
        assert "not valid gdscript" in result.source

    def test_empty_file_parses_successfully(self, fixture_project: ProjectFiles) -> None:
        empty_path = next(p for p in fixture_project.gd_files if p.name == "empty_file.gd")
        result = parse_file(empty_path, fixture_project.to_res_path(empty_path))

        assert result.tree is not None
        assert isinstance(result.tree, Tree)
        assert result.error is None

    def test_empty_file_has_empty_source(self, fixture_project: ProjectFiles) -> None:
        empty_path = next(p for p in fixture_project.gd_files if p.name == "empty_file.gd")
        result = parse_file(empty_path, fixture_project.to_res_path(empty_path))

        assert result.source == ""

    def test_returns_parse_result_dataclass(self, fixture_project: ProjectFiles) -> None:
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert isinstance(result, ParseResult)

    def test_parse_error_logs_warning(self, fixture_project: ProjectFiles, caplog: pytest.LogCaptureFixture) -> None:
        error_path = next(p for p in fixture_project.gd_files if p.name == "parse_error.gd")

        with caplog.at_level(logging.WARNING, logger="gdscript_code_graph.parsing"):
            pr = parse_file(error_path, fixture_project.to_res_path(error_path))

        assert pr.error is not None
        assert len(caplog.records) == 1
        assert "Failed to parse" in caplog.records[0].message


class TestParseAll:
    def test_returns_seven_results(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        assert len(results) == 7

    def test_exactly_one_failure(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        failures = [r for r in results if r.tree is None]
        assert len(failures) == 1
        assert failures[0].file_path.name == "parse_error.gd"

    def test_six_successes(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        successes = [r for r in results if r.tree is not None]
        assert len(successes) == 6

    def test_all_results_have_source(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        for result in results:
            # Every result has source populated (even parse errors, since
            # parse_error.gd is valid UTF-8). The only exception is
            # empty_file.gd which has source == "".
            if result.file_path.name == "empty_file.gd":
                assert result.source == ""
            else:
                assert len(result.source) > 0

    def test_all_results_have_res_path(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        for result in results:
            assert result.res_path.startswith("res://")
            assert result.res_path.endswith(".gd")

    def test_res_paths_match_expected(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        res_paths = sorted(r.res_path for r in results)
        expected = sorted([
            "res://actors/character.gd",
            "res://actors/enemy.gd",
            "res://actors/player.gd",
            "res://empty_file.gd",
            "res://parse_error.gd",
            "res://utils/helpers.gd",
            "res://weapons/bullet.gd",
        ])
        assert res_paths == expected

    def test_all_results_are_parse_result(self, fixture_project: ProjectFiles) -> None:
        results = parse_all(fixture_project)

        for result in results:
            assert isinstance(result, ParseResult)

    def test_never_aborts_on_error(self, fixture_project: ProjectFiles) -> None:
        """Verify that parse_all processes all files even when some fail."""
        results = parse_all(fixture_project)

        # Even though parse_error.gd fails, we still get results for all 7 files
        assert len(results) == 7
        file_names = [r.file_path.name for r in results]
        assert "parse_error.gd" in file_names
        assert "player.gd" in file_names


class TestParseFileEdgeCases:
    def test_unicode_error_captured(self, tmp_path: Path) -> None:
        """A file with invalid UTF-8 should produce an error, not raise."""
        bad_file = tmp_path / "bad_encoding.gd"
        bad_file.write_bytes(b"\xff\xfe\x00\x01 extends Node\n")
        result = parse_file(bad_file, "res://bad_encoding.gd")

        assert result.tree is None
        assert result.error is not None
        assert result.source == ""

    def test_unicode_error_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """A file with invalid UTF-8 should log a warning."""
        bad_file = tmp_path / "bad_encoding.gd"
        bad_file.write_bytes(b"\xff\xfe\x00\x01 extends Node\n")

        with caplog.at_level(logging.WARNING, logger="gdscript_code_graph.parsing"):
            result = parse_file(bad_file, "res://bad_encoding.gd")

        assert result.error is not None
        assert len(caplog.records) == 1
        assert "Failed to read" in caplog.records[0].message

    def test_all_fixture_files_have_gather_metadata(
        self, fixture_project: ProjectFiles
    ) -> None:
        """Verify that gather_metadata=True produces trees with metadata."""
        player_path = next(p for p in fixture_project.gd_files if p.name == "player.gd")
        result = parse_file(player_path, fixture_project.to_res_path(player_path))

        assert result.tree is not None
        # The tree root should be a 'start' rule; children should have
        # meta information (line numbers) thanks to gather_metadata=True.
        assert result.tree.data == "start"
        # At least one child node should have .meta with .line attribute
        has_meta = False
        for child in result.tree.iter_subtrees():
            if hasattr(child, "meta") and hasattr(child.meta, "line"):
                has_meta = True
                break
        assert has_meta, "gather_metadata=True should produce .meta.line on nodes"
