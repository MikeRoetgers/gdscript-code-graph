import logging
from pathlib import Path

from gdtoolkit.parser import parser as gdparser

from gdscript_code_graph.discovery import ProjectFiles
from gdscript_code_graph.parsing import ParseResult, parse_all, parse_file
from gdscript_code_graph.relationships import (
    RawRelationship,
    extract_type_from_hint,
    build_class_name_table,
    extract_class_name,
    extract_extends,
    extract_preloads,
    extract_returns,
    extract_typed_deps,
    resolve_relationships_with_evidence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_fixture(project: ProjectFiles, filename: str):
    """Parse a fixture file and return a ParseResult."""
    file_path = next(p for p in project.gd_files if p.name == filename)
    return parse_file(file_path, project.to_res_path(file_path))


# ---------------------------------------------------------------------------
# extract_class_name
# ---------------------------------------------------------------------------


class TestExtractClassName:
    def test_character_has_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "character.gd")
        assert pr.tree is not None
        assert extract_class_name(pr.tree) == "Character"

    def test_player_has_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "player.gd")
        assert pr.tree is not None
        assert extract_class_name(pr.tree) == "Player"

    def test_bullet_has_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "bullet.gd")
        assert pr.tree is not None
        assert extract_class_name(pr.tree) == "Bullet"

    def test_enemy_has_no_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "enemy.gd")
        assert pr.tree is not None
        assert extract_class_name(pr.tree) is None

    def test_helpers_has_no_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "helpers.gd")
        assert pr.tree is not None
        assert extract_class_name(pr.tree) is None

    def test_classname_extends_stmt(self) -> None:
        """class_name Foo extends Bar should extract 'Foo' as the class name."""
        source = 'class_name Foo extends Bar\n'
        tree = gdparser.parse(source, gather_metadata=True)
        assert extract_class_name(tree) == "Foo"


# ---------------------------------------------------------------------------
# extract_extends
# ---------------------------------------------------------------------------


class TestExtractExtends:
    def test_player_extends_by_class_name(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "player.gd")
        assert pr.tree is not None
        rels = extract_extends(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "Character"
        assert rels[0].kind == "extends"
        assert rels[0].source_res_path == "res://actors/player.gd"
        assert rels[0].line == 1

    def test_enemy_extends_by_path(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "enemy.gd")
        assert pr.tree is not None
        rels = extract_extends(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "res://actors/character.gd"
        assert rels[0].kind == "extends"
        assert rels[0].source_res_path == "res://actors/enemy.gd"
        assert rels[0].line == 1

    def test_character_extends_builtin(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "character.gd")
        assert pr.tree is not None
        rels = extract_extends(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "Node2D"
        assert rels[0].kind == "extends"

    def test_bullet_extends_builtin(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "bullet.gd")
        assert pr.tree is not None
        rels = extract_extends(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "Area2D"
        assert rels[0].kind == "extends"

    def test_helpers_has_no_extends(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "helpers.gd")
        assert pr.tree is not None
        rels = extract_extends(pr.tree, pr.res_path)

        assert len(rels) == 0

    def test_classname_extends_stmt(self) -> None:
        """class_name Foo extends Bar should produce an extends relationship to 'Bar'."""
        source = 'class_name Foo extends Bar\n'
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_extends(tree, "res://foo.gd")

        assert len(rels) == 1
        assert rels[0].target == "Bar"
        assert rels[0].kind == "extends"


# ---------------------------------------------------------------------------
# extract_preloads
# ---------------------------------------------------------------------------


class TestExtractPreloads:
    def test_player_preloads_bullet(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "player.gd")
        assert pr.tree is not None
        rels = extract_preloads(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "res://weapons/bullet.gd"
        assert rels[0].kind == "preloads"
        assert rels[0].source_res_path == "res://actors/player.gd"
        assert rels[0].line == 4

    def test_helpers_preloads_character(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "helpers.gd")
        assert pr.tree is not None
        rels = extract_preloads(pr.tree, pr.res_path)

        assert len(rels) == 1
        assert rels[0].target == "res://actors/character.gd"
        assert rels[0].kind == "preloads"
        assert rels[0].source_res_path == "res://utils/helpers.gd"
        assert rels[0].line == 1

    def test_enemy_has_no_preloads(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "enemy.gd")
        assert pr.tree is not None
        rels = extract_preloads(pr.tree, pr.res_path)

        assert len(rels) == 0

    def test_character_has_no_preloads(self, fixture_project: ProjectFiles) -> None:
        pr = _parse_fixture(fixture_project, "character.gd")
        assert pr.tree is not None
        rels = extract_preloads(pr.tree, pr.res_path)

        assert len(rels) == 0

    def test_load_call_detected(self) -> None:
        """Bare load() call should be detected with kind='loads'."""
        source = 'func f():\n\tvar x = load("res://test.gd")\n'
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_preloads(tree, "res://test_file.gd")

        assert len(rels) == 1
        assert rels[0].target == "res://test.gd"
        assert rels[0].kind == "loads"

    def test_resource_loader_load_detected(self) -> None:
        """ResourceLoader.load() should be detected with kind='loads'."""
        source = 'func f():\n\tvar x = ResourceLoader.load("res://test.gd")\n'
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_preloads(tree, "res://test_file.gd")

        assert len(rels) == 1
        assert rels[0].target == "res://test.gd"
        assert rels[0].kind == "loads"

    def test_preload_with_user_path_ignored(self) -> None:
        """preload() with user:// path should be skipped."""
        source = 'func f():\n\tvar x = preload("user://saves/data.gd")\n'
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_preloads(tree, "res://test_file.gd")
        assert len(rels) == 0

    def test_load_with_relative_path_ignored(self) -> None:
        """load() with a relative path (no res:// prefix) should be skipped."""
        source = 'func f():\n\tvar x = load("relative/path.gd")\n'
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_preloads(tree, "res://test_file.gd")
        assert len(rels) == 0

    def test_preload_with_res_path_among_others(self) -> None:
        """Only res:// paths should be returned when mixed with non-res:// paths."""
        source = (
            'var a = preload("res://weapons/bullet.gd")\n'
            'func f():\n'
            '\tvar b = load("user://saves/data.gd")\n'
        )
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_preloads(tree, "res://test_file.gd")

        assert len(rels) == 1
        assert rels[0].target == "res://weapons/bullet.gd"
        assert rels[0].kind == "preloads"


# ---------------------------------------------------------------------------
# extract_type_from_hint
# ---------------------------------------------------------------------------


class TestExtractTypeFromHint:
    def test_plain_type(self) -> None:
        """Plain type name like 'Player' is returned as-is."""
        assert extract_type_from_hint("Player") == "Player"

    def test_array_with_inner_type(self) -> None:
        """Array[Item] extracts the inner type 'Item'."""
        assert extract_type_from_hint("Array[Item]") == "Item"

    def test_bare_array(self) -> None:
        """Bare 'Array' without brackets is returned as-is."""
        assert extract_type_from_hint("Array") == "Array"

    def test_dictionary_type(self) -> None:
        """Plain 'Dictionary' type is returned as-is."""
        assert extract_type_from_hint("Dictionary") == "Dictionary"

    def test_array_with_builtin_inner(self) -> None:
        """Array[int] extracts the built-in inner type 'int'."""
        assert extract_type_from_hint("Array[int]") == "int"

    def test_nested_array_returns_partial_match(self) -> None:
        """Nested Array[Array[int]] is not fully supported in v1.

        The regex only captures the outer Array's inner type as 'Array',
        which will not resolve to a project class and be filtered out.
        This is a known limitation.
        """
        result = extract_type_from_hint("Array[Array[int]]")
        # Doesn't match the regex because inner contains brackets
        assert result == "Array[Array[int]]"


# ---------------------------------------------------------------------------
# build_class_name_table
# ---------------------------------------------------------------------------


class TestBuildClassNameTable:
    def test_full_fixture_set(self, fixture_project: ProjectFiles) -> None:
        parse_results = parse_all(fixture_project)
        table = build_class_name_table(parse_results)

        assert table == {
            "Character": "res://actors/character.gd",
            "Player": "res://actors/player.gd",
            "Bullet": "res://weapons/bullet.gd",
        }

    def test_skips_files_without_class_name(self, fixture_project: ProjectFiles) -> None:
        parse_results = parse_all(fixture_project)
        table = build_class_name_table(parse_results)

        # enemy.gd and helpers.gd have no class_name
        values = set(table.values())
        assert "res://actors/enemy.gd" not in values
        assert "res://utils/helpers.gd" not in values

    def test_skips_failed_parses(self, fixture_project: ProjectFiles) -> None:
        parse_results = parse_all(fixture_project)
        table = build_class_name_table(parse_results)

        # parse_error.gd has tree=None, so it should be skipped
        values = set(table.values())
        assert "res://parse_error.gd" not in values

    def test_duplicate_class_name_last_wins(self, caplog) -> None:
        """Two files declaring the same class_name should log a warning and use last-wins."""

        source_a = "class_name Duplicate\n"
        source_b = "class_name Duplicate\n"

        pr_a = ParseResult(
            file_path=Path("/fake/first.gd"),
            res_path="res://first.gd",
            source=source_a,
            tree=gdparser.parse(source_a, gather_metadata=True),
            error=None,
        )
        pr_b = ParseResult(
            file_path=Path("/fake/second.gd"),
            res_path="res://second.gd",
            source=source_b,
            tree=gdparser.parse(source_b, gather_metadata=True),
            error=None,
        )

        with caplog.at_level(logging.WARNING, logger="gdscript_code_graph.relationships"):
            table = build_class_name_table([pr_a, pr_b])

        # Last-wins: the second file's res_path should be in the table
        assert len(table) == 1
        assert table["Duplicate"] == "res://second.gd"

        # Exactly one warning should have been logged at WARNING level
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

        # Warning mentions the duplicate name and both paths
        assert "Duplicate" in caplog.text
        assert "res://first.gd" in caplog.text
        assert "res://second.gd" in caplog.text


# ---------------------------------------------------------------------------
# extract_typed_deps
# ---------------------------------------------------------------------------


class TestExtractTypedDeps:
    def test_simple_typed_variable(self) -> None:
        """var x: Type should produce a typed_dependency relationship."""

        source = "var player: Player\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Player"
        assert rels[0].kind == "typed_dependency"
        assert rels[0].source_res_path == "res://test.gd"

    def test_typed_variable_with_assignment(self) -> None:
        """var x: Type = value should produce a typed_dependency relationship."""

        source = "var enemy: Enemy = null\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Enemy"
        assert rels[0].kind == "typed_dependency"

    def test_array_type_extracts_inner(self) -> None:
        """var x: Array[Type] should extract the inner type."""

        source = "var items: Array[Item]\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Item"
        assert rels[0].kind == "typed_dependency"

    def test_builtin_type_still_emitted(self) -> None:
        """Built-in types are emitted (filtering happens during resolution)."""

        source = "var speed: float = 200.0\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "float"

    def test_multiple_typed_vars(self) -> None:
        """Multiple typed variables produce multiple relationships."""

        source = "var a: Foo\nvar b: Bar = null\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 2
        targets = {r.target for r in rels}
        assert targets == {"Foo", "Bar"}

    def test_player_fixture_has_bullet_dep(self, fixture_project: ProjectFiles) -> None:
        """player.gd has var active_bullet: Bullet."""
        pr = _parse_fixture(fixture_project, "player.gd")
        assert pr.tree is not None
        rels = extract_typed_deps(pr.tree, pr.res_path)

        bullet_rels = [r for r in rels if r.target == "Bullet"]
        assert len(bullet_rels) == 1
        assert bullet_rels[0].kind == "typed_dependency"
        assert bullet_rels[0].line == 8

    def test_line_numbers(self) -> None:
        """Each relationship should carry the correct line number."""

        source = "var a: Foo\nvar b: int = 0\nvar c: Bar\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 3
        # Lines should be 1, 2, 3
        lines = [r.line for r in rels]
        assert lines == [1, 2, 3]

    def test_ignores_func_local_vars(self) -> None:
        """Function-local typed variables should NOT be extracted.

        Only class-level vars (class_var_typed) are composition dependencies.
        """

        source = "func f():\n\tvar x: Player = null\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_typed_deps(tree, "res://test.gd")

        assert len(rels) == 0


# ---------------------------------------------------------------------------
# extract_returns
# ---------------------------------------------------------------------------


class TestExtractReturns:
    def test_simple_return_type(self) -> None:
        """func foo() -> Type should produce a returns relationship."""

        source = "func get_weapon() -> Weapon:\n\treturn null\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Weapon"
        assert rels[0].kind == "returns"
        assert rels[0].source_res_path == "res://test.gd"

    def test_array_return_type(self) -> None:
        """func foo() -> Array[Type] should extract the inner type."""

        source = "func get_items() -> Array[Item]:\n\treturn []\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Item"
        assert rels[0].kind == "returns"

    def test_void_return_type_still_emitted(self) -> None:
        """void return types are emitted (filtering happens during resolution)."""

        source = "func process() -> void:\n\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "void"

    def test_no_return_type_produces_nothing(self) -> None:
        """func foo(): (no return type) should produce no relationship."""

        source = "func foo():\n\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 0

    def test_multiple_functions(self) -> None:
        """Multiple functions with return types produce multiple relationships."""

        source = (
            "func a() -> Foo:\n\treturn null\n"
            "func b() -> Bar:\n\treturn null\n"
        )
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 2
        targets = {r.target for r in rels}
        assert targets == {"Foo", "Bar"}

    def test_character_fixture_returns_bullet(self, fixture_project: ProjectFiles) -> None:
        """character.gd has get_bullet() -> Bullet."""
        pr = _parse_fixture(fixture_project, "character.gd")
        assert pr.tree is not None
        rels = extract_returns(pr.tree, pr.res_path)

        bullet_rels = [r for r in rels if r.target == "Bullet"]
        assert len(bullet_rels) == 1
        assert bullet_rels[0].kind == "returns"
        assert bullet_rels[0].line == 11

    def test_player_fixture_returns_bullet(self, fixture_project: ProjectFiles) -> None:
        """player.gd has shoot() -> Bullet."""
        pr = _parse_fixture(fixture_project, "player.gd")
        assert pr.tree is not None
        rels = extract_returns(pr.tree, pr.res_path)

        bullet_rels = [r for r in rels if r.target == "Bullet"]
        assert len(bullet_rels) == 1
        assert bullet_rels[0].kind == "returns"
        assert bullet_rels[0].line == 18

    def test_line_numbers(self) -> None:
        """Each relationship should carry the correct line number."""

        source = (
            "func a() -> Foo:\n\treturn null\n"
            "func b() -> Bar:\n\treturn null\n"
        )
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert rels[0].line == 1
        assert rels[1].line == 3

    def test_ignores_parameter_type_hints(self) -> None:
        """Only return type should be extracted, not parameter types."""

        source = "func shoot(target: Enemy, power: float) -> Bullet:\n\treturn null\n"
        tree = gdparser.parse(source, gather_metadata=True)
        rels = extract_returns(tree, "res://test.gd")

        assert len(rels) == 1
        assert rels[0].target == "Bullet"


# ---------------------------------------------------------------------------
# resolve_relationships_with_evidence
# ---------------------------------------------------------------------------


class TestResolveRelationshipsWithEvidence:
    def test_collects_all_evidence(self) -> None:
        """Duplicate (source, target, kind) tuples produce multiple evidence entries."""
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="preloads",
                line=1,
            ),
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="preloads",
                line=5,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd", "res://b.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 1
        assert links[0].weight == 2
        assert len(links[0].evidence) == 2
        assert links[0].evidence[0].line == 1
        assert links[0].evidence[1].line == 5

    def test_different_kinds_produce_separate_links(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="preloads",
                line=1,
            ),
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="extends",
                line=2,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd", "res://b.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 2

    def test_resolves_class_name(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://actors/player.gd",
                target="Character",
                kind="extends",
                line=1,
            ),
        ]
        table = {"Character": "res://actors/character.gd"}
        known = {"res://actors/player.gd", "res://actors/character.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 1
        assert links[0].source == "res://actors/player.gd"
        assert links[0].target == "res://actors/character.gd"
        assert links[0].kind == "extends"
        assert links[0].evidence[0].line == 1

    def test_skips_builtin_classes(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="Node2D",
                kind="extends",
                line=1,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 0

    def test_skips_unknown_res_path(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://nonexistent.gd",
                kind="preloads",
                line=1,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 0

    def test_extends_by_path_resolves(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://actors/enemy.gd",
                target="res://actors/character.gd",
                kind="extends",
                line=1,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://actors/enemy.gd", "res://actors/character.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 1
        assert links[0].source == "res://actors/enemy.gd"
        assert links[0].target == "res://actors/character.gd"
        assert links[0].kind == "extends"

    def test_preload_with_res_path_resolves(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://actors/player.gd",
                target="res://weapons/bullet.gd",
                kind="preloads",
                line=4,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://actors/player.gd", "res://weapons/bullet.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 1
        assert links[0].target == "res://weapons/bullet.gd"
        assert links[0].kind == "preloads"

    def test_links_are_sorted(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://z.gd",
                target="res://b.gd",
                kind="preloads",
                line=1,
            ),
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="preloads",
                line=1,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd", "res://b.gd", "res://z.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert len(links) == 2
        assert links[0].source == "res://a.gd"
        assert links[1].source == "res://z.gd"

    def test_evidence_file_matches_source(self) -> None:
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://b.gd",
                kind="preloads",
                line=3,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd", "res://b.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        assert links[0].evidence[0].file == "res://a.gd"
        assert links[0].evidence[0].line == 3


# ---------------------------------------------------------------------------
# Self-referencing link (self-loop) tests
# ---------------------------------------------------------------------------


class TestSelfLoop:
    def test_self_preload_produces_link(self) -> None:
        """A file that preloads itself should produce a valid link."""
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://a.gd",
                kind="preloads",
                line=5,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)

        # Document expected behavior: self-links are allowed
        assert len(links) == 1
        assert links[0].source == "res://a.gd"
        assert links[0].target == "res://a.gd"

    def test_self_extends_produces_link(self) -> None:
        """A file that extends itself (unusual but possible) should be handled."""
        raw = [
            RawRelationship(
                source_res_path="res://a.gd",
                target="res://a.gd",
                kind="extends",
                line=1,
            ),
        ]
        table: dict[str, str] = {}
        known = {"res://a.gd"}

        links = resolve_relationships_with_evidence(raw, table, known)
        assert len(links) == 1
