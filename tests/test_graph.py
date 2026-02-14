import json
from datetime import datetime
from pathlib import Path

import pytest

from gdscript_code_graph.discovery import discover_project
from gdscript_code_graph.graph import build_graph, serialize_graph
from gdscript_code_graph.schema import Graph, GraphLink, GraphNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_graph(fixtures_dir: Path) -> Graph:
    """Build the Graph once and share it across all tests in this module."""
    project = discover_project(fixtures_dir)
    return build_graph(project, repo_name="test-game")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_node(graph: Graph, node_id: str) -> GraphNode:
    """Find a node in the graph by its ID."""
    for node in graph.nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"Node {node_id!r} not found in graph")


def _find_link(
    graph: Graph, source: str, target: str, kind: str
) -> GraphLink:
    """Find a link in the graph by source, target, and kind."""
    for link in graph.links:
        if link.source == source and link.target == target and link.kind == kind:
            return link
    raise ValueError(
        f"Link ({source!r} -> {target!r}, kind={kind!r}) not found in graph"
    )


# ---------------------------------------------------------------------------
# Full pipeline test
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_schema_version(self, fixture_graph: Graph) -> None:
        assert fixture_graph.schema_version == "1.0"

    def test_meta_repo(self, fixture_graph: Graph) -> None:
        assert fixture_graph.meta.repo == "test-game"

    def test_meta_generated_at_is_valid_iso8601(self, fixture_graph: Graph) -> None:
        # Should parse without error
        parsed = datetime.fromisoformat(fixture_graph.meta.generated_at)
        assert parsed is not None

    def test_node_count(self, fixture_graph: Graph) -> None:
        assert len(fixture_graph.nodes) == 7


# ---------------------------------------------------------------------------
# Empty project test
# ---------------------------------------------------------------------------


class TestEmptyProject:
    def test_empty_project_produces_empty_graph(self, tmp_path) -> None:
        """A project with no .gd files should produce an empty graph, not an error."""
        (tmp_path / "project.godot").write_text("")
        project = discover_project(tmp_path)
        graph = build_graph(project, "empty")
        assert len(graph.nodes) == 0
        assert len(graph.links) == 0


# ---------------------------------------------------------------------------
# Node IDs test
# ---------------------------------------------------------------------------


class TestNodeIDs:
    EXPECTED_IDS = {
        "res://actors/character.gd",
        "res://actors/player.gd",
        "res://actors/enemy.gd",
        "res://weapons/bullet.gd",
        "res://utils/helpers.gd",
        "res://empty_file.gd",
        "res://parse_error.gd",
    }

    def test_all_expected_node_ids_present(self, fixture_graph: Graph) -> None:
        actual_ids = {node.id for node in fixture_graph.nodes}
        assert actual_ids == self.EXPECTED_IDS


# ---------------------------------------------------------------------------
# Node name test
# ---------------------------------------------------------------------------


class TestNodeNames:
    def test_character_name_from_class_name(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://actors/character.gd")
        assert node.name == "Character"

    def test_player_name_from_class_name(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://actors/player.gd")
        assert node.name == "Player"

    def test_bullet_name_from_class_name(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://weapons/bullet.gd")
        assert node.name == "Bullet"

    def test_enemy_name_from_stem(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://actors/enemy.gd")
        assert node.name == "enemy"

    def test_empty_file_name_from_stem(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://empty_file.gd")
        assert node.name == "empty_file"

    def test_parse_error_name_from_stem(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.name == "parse_error"

    def test_helpers_name_from_stem(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://utils/helpers.gd")
        assert node.name == "helpers"


# ---------------------------------------------------------------------------
# Node metrics test
# ---------------------------------------------------------------------------


class TestNodeMetrics:
    def test_empty_file_has_zero_loc(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://empty_file.gd")
        assert node.metrics.loc == 0

    def test_parse_error_has_none_cc(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.metrics.max_cc is None
        assert node.metrics.median_cc is None

    def test_parse_error_has_positive_loc(self, fixture_graph: Graph) -> None:
        """Even files that fail to parse still get LOC from raw source text."""
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.metrics.loc > 0

    def test_bullet_has_positive_loc(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://weapons/bullet.gd")
        assert node.metrics.loc > 0

    def test_bullet_has_cc(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://weapons/bullet.gd")
        assert node.metrics.max_cc is not None
        assert node.metrics.median_cc is not None

    def test_mi_is_computed_for_valid_files(self, fixture_graph: Graph) -> None:
        valid_ids = {
            "res://actors/character.gd",
            "res://actors/player.gd",
            "res://actors/enemy.gd",
            "res://weapons/bullet.gd",
            "res://utils/helpers.gd",
        }
        for node in fixture_graph.nodes:
            if node.id in valid_ids:
                assert node.metrics.mi is not None, f"{node.id} should have MI"
                assert isinstance(node.metrics.mi, float)
                assert 0 <= node.metrics.mi <= 171

    def test_mi_is_none_for_parse_error(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.metrics.mi is None

    def test_mi_is_none_for_empty_file(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://empty_file.gd")
        assert node.metrics.mi is None

    def test_mi_min_and_mi_median_for_valid_files(self, fixture_graph: Graph) -> None:
        valid_ids = {
            "res://actors/character.gd",
            "res://actors/player.gd",
            "res://actors/enemy.gd",
            "res://weapons/bullet.gd",
            "res://utils/helpers.gd",
        }
        for node in fixture_graph.nodes:
            if node.id in valid_ids:
                assert node.metrics.mi_min is not None, f"{node.id} should have mi_min"
                assert node.metrics.mi_median is not None, f"{node.id} should have mi_median"
                assert 0 <= node.metrics.mi_min <= 171
                assert 0 <= node.metrics.mi_median <= 171

    def test_mi_min_is_none_for_parse_error(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.metrics.mi_min is None
        assert node.metrics.mi_median is None

    def test_mi_min_is_none_for_empty_file(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://empty_file.gd")
        assert node.metrics.mi_min is None
        assert node.metrics.mi_median is None

    def test_functions_list_for_player(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://actors/player.gd")
        names = {f.name for f in node.metrics.functions}
        assert names == {"_process", "shoot"}

    def test_functions_list_empty_for_parse_error(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://parse_error.gd")
        assert node.metrics.functions == []

    def test_functions_list_empty_for_empty_file(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://empty_file.gd")
        assert node.metrics.functions == []

    def test_function_metrics_have_all_fields(self, fixture_graph: Graph) -> None:
        node = _find_node(fixture_graph, "res://actors/character.gd")
        for func in node.metrics.functions:
            assert isinstance(func.name, str)
            assert isinstance(func.line, int)
            assert isinstance(func.cc, int)
            assert isinstance(func.loc, int)
            assert func.cc >= 1
            assert func.loc >= 1

    def test_tags_are_always_empty(self, fixture_graph: Graph) -> None:
        for node in fixture_graph.nodes:
            assert node.tags == []

    def test_all_nodes_are_script_kind(self, fixture_graph: Graph) -> None:
        for node in fixture_graph.nodes:
            assert node.kind == "script"

    def test_all_nodes_are_gdscript_language(self, fixture_graph: Graph) -> None:
        for node in fixture_graph.nodes:
            assert node.language == "gdscript"


# ---------------------------------------------------------------------------
# Links test
# ---------------------------------------------------------------------------


class TestLinks:
    def test_link_count(self, fixture_graph: Graph) -> None:
        assert len(fixture_graph.links) == 7

    def test_player_extends_character(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://actors/character.gd",
            "extends",
        )
        assert link.weight == 1

    def test_enemy_extends_character(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/enemy.gd",
            "res://actors/character.gd",
            "extends",
        )
        assert link.weight == 1

    def test_player_preloads_bullet(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://weapons/bullet.gd",
            "preloads",
        )
        assert link.weight == 1

    def test_helpers_preloads_character(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://utils/helpers.gd",
            "res://actors/character.gd",
            "preloads",
        )
        assert link.weight == 1

    def test_player_typed_dep_bullet(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://weapons/bullet.gd",
            "typed_dependency",
        )
        assert link.weight == 1

    def test_player_returns_bullet(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://weapons/bullet.gd",
            "returns",
        )
        assert link.weight == 1

    def test_character_returns_bullet(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/character.gd",
            "res://weapons/bullet.gd",
            "returns",
        )
        assert link.weight == 1

    def test_no_links_to_builtin_node2d(self, fixture_graph: Graph) -> None:
        for link in fixture_graph.links:
            assert link.target != "Node2D"

    def test_no_links_to_builtin_area2d(self, fixture_graph: Graph) -> None:
        for link in fixture_graph.links:
            assert link.target != "Area2D"

    def test_no_links_for_builtin_return_types(self, fixture_graph: Graph) -> None:
        """Return types like void, bool, int should not produce links."""
        builtin_targets = {"void", "bool", "int", "float", "String"}
        for link in fixture_graph.links:
            assert link.target not in builtin_targets

    def test_no_links_for_builtin_typed_deps(self, fixture_graph: Graph) -> None:
        """Typed deps like int, float should not produce links."""
        builtin_targets = {"int", "float", "String", "Array", "Vector2"}
        for link in fixture_graph.links:
            assert link.target not in builtin_targets


# ---------------------------------------------------------------------------
# Evidence test
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_each_link_has_at_least_one_evidence(self, fixture_graph: Graph) -> None:
        for link in fixture_graph.links:
            assert len(link.evidence) >= 1

    def test_evidence_has_file_and_line(self, fixture_graph: Graph) -> None:
        for link in fixture_graph.links:
            for ev in link.evidence:
                assert ev.file is not None
                assert isinstance(ev.file, str)
                assert ev.line is not None
                assert isinstance(ev.line, int)

    def test_evidence_file_matches_link_source(self, fixture_graph: Graph) -> None:
        for link in fixture_graph.links:
            for ev in link.evidence:
                assert ev.file == link.source

    def test_player_extends_evidence_line(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://actors/character.gd",
            "extends",
        )
        assert link.evidence[0].line == 1

    def test_player_preload_evidence_line(self, fixture_graph: Graph) -> None:
        link = _find_link(
            fixture_graph,
            "res://actors/player.gd",
            "res://weapons/bullet.gd",
            "preloads",
        )
        assert link.evidence[0].line == 4


# ---------------------------------------------------------------------------
# JSON round-trip test
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_serialize_produces_valid_json(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    def test_serialized_has_expected_top_level_keys(
        self, fixture_graph: Graph
    ) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert set(parsed.keys()) == {
            "schema_version",
            "meta",
            "nodes",
            "links",
        }

    def test_serialized_schema_version(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert parsed["schema_version"] == "1.0"

    def test_serialized_node_count(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert len(parsed["nodes"]) == 7

    def test_serialized_link_count(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert len(parsed["links"]) == 7

    def test_serialized_meta_has_repo(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        assert parsed["meta"]["repo"] == "test-game"

    def test_serialized_node_has_expected_fields(
        self, fixture_graph: Graph
    ) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        node = parsed["nodes"][0]
        assert "id" in node
        assert "kind" in node
        assert "language" in node
        assert "name" in node
        assert "metrics" in node
        assert "tags" in node

    def test_serialized_link_has_expected_fields(
        self, fixture_graph: Graph
    ) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        link = parsed["links"][0]
        assert "source" in link
        assert "target" in link
        assert "kind" in link
        assert "weight" in link
        assert "evidence" in link

    def test_serialized_mi_values(self, fixture_graph: Graph) -> None:
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        nodes_by_id = {n["id"]: n for n in parsed["nodes"]}

        # Valid files should have float MI in JSON
        valid_ids = [
            "res://actors/character.gd",
            "res://actors/player.gd",
            "res://actors/enemy.gd",
            "res://weapons/bullet.gd",
            "res://utils/helpers.gd",
        ]
        for node_id in valid_ids:
            mi = nodes_by_id[node_id]["metrics"]["mi"]
            assert isinstance(mi, float), f"{node_id} MI should be a float"
            assert 0 <= mi <= 171

        # Parse error and empty file should have null MI in JSON
        assert nodes_by_id["res://parse_error.gd"]["metrics"]["mi"] is None
        assert nodes_by_id["res://empty_file.gd"]["metrics"]["mi"] is None

    def test_serialized_cc_fields(self, fixture_graph: Graph) -> None:
        """Serialized output uses max_cc and median_cc instead of cc."""
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        nodes_by_id = {n["id"]: n for n in parsed["nodes"]}

        # Valid files have integer max_cc and float median_cc
        valid_ids = [
            "res://actors/character.gd",
            "res://actors/player.gd",
            "res://actors/enemy.gd",
            "res://weapons/bullet.gd",
            "res://utils/helpers.gd",
        ]
        for node_id in valid_ids:
            metrics = nodes_by_id[node_id]["metrics"]
            assert "max_cc" in metrics, f"{node_id} missing max_cc"
            assert "median_cc" in metrics, f"{node_id} missing median_cc"
            assert "cc" not in metrics, f"{node_id} should not have old cc field"
            assert isinstance(metrics["max_cc"], int)
            assert isinstance(metrics["median_cc"], (int, float))

        # Parse error has null for both
        pe = nodes_by_id["res://parse_error.gd"]["metrics"]
        assert pe["max_cc"] is None
        assert pe["median_cc"] is None

    def test_serialized_mi_min_and_mi_median(self, fixture_graph: Graph) -> None:
        """Serialized output includes mi_min and mi_median."""
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        nodes_by_id = {n["id"]: n for n in parsed["nodes"]}

        valid_ids = [
            "res://actors/character.gd",
            "res://actors/player.gd",
            "res://actors/enemy.gd",
            "res://weapons/bullet.gd",
            "res://utils/helpers.gd",
        ]
        for node_id in valid_ids:
            metrics = nodes_by_id[node_id]["metrics"]
            assert "mi_min" in metrics, f"{node_id} missing mi_min"
            assert "mi_median" in metrics, f"{node_id} missing mi_median"
            assert isinstance(metrics["mi_min"], float)
            assert isinstance(metrics["mi_median"], float)

        # Parse error and empty file have null
        assert nodes_by_id["res://parse_error.gd"]["metrics"]["mi_min"] is None
        assert nodes_by_id["res://parse_error.gd"]["metrics"]["mi_median"] is None
        assert nodes_by_id["res://empty_file.gd"]["metrics"]["mi_min"] is None
        assert nodes_by_id["res://empty_file.gd"]["metrics"]["mi_median"] is None

    def test_serialized_functions_array(self, fixture_graph: Graph) -> None:
        """Serialized output includes functions array with per-function detail."""
        serialized = serialize_graph(fixture_graph)
        parsed = json.loads(serialized)
        nodes_by_id = {n["id"]: n for n in parsed["nodes"]}

        # Player should have 2 functions
        player = nodes_by_id["res://actors/player.gd"]
        funcs = player["metrics"]["functions"]
        assert len(funcs) == 2
        func_names = {f["name"] for f in funcs}
        assert func_names == {"_process", "shoot"}

        # Each function should have all expected fields
        for f in funcs:
            assert "name" in f
            assert "line" in f
            assert "cc" in f
            assert "loc" in f
            assert "mi" in f
            assert isinstance(f["cc"], int)
            assert isinstance(f["loc"], int)
            assert isinstance(f["line"], int)

        # Parse error and empty file have empty functions lists
        assert nodes_by_id["res://parse_error.gd"]["metrics"]["functions"] == []
        assert nodes_by_id["res://empty_file.gd"]["metrics"]["functions"] == []
