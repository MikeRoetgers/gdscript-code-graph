import pytest
from pathlib import Path

from gdscript_code_graph.discovery import (
    ProjectFiles,
    find_project_root,
    discover_project,
)


class TestFindProjectRoot:
    def test_finds_root_from_fixtures_dir(self, fixtures_dir: Path) -> None:
        root = find_project_root(fixtures_dir)
        assert root == fixtures_dir.resolve()
        assert (root / "project.godot").exists()

    def test_finds_root_from_subdirectory(self, fixtures_dir: Path) -> None:
        sub_dir = fixtures_dir / "actors"
        root = find_project_root(sub_dir)
        assert root == fixtures_dir.resolve()

    def test_raises_when_no_project_godot(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No project.godot found"):
            find_project_root(tmp_path)


class TestDiscoverProject:
    def test_finds_all_seven_gd_files(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        assert len(project.gd_files) == 7

    def test_excludes_godot_directory(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        for gd_file in project.gd_files:
            assert ".godot" not in gd_file.parts

    def test_files_are_sorted(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        paths_as_strings = [str(p) for p in project.gd_files]
        assert paths_as_strings == sorted(paths_as_strings)

    def test_expected_filenames(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        filenames = [p.name for p in project.gd_files]
        assert "character.gd" in filenames
        assert "player.gd" in filenames
        assert "enemy.gd" in filenames
        assert "bullet.gd" in filenames
        assert "helpers.gd" in filenames
        assert "empty_file.gd" in filenames
        assert "parse_error.gd" in filenames

    def test_project_root_is_fixtures_dir(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        assert project.project_root == fixtures_dir.resolve()

    def test_all_paths_are_absolute(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        for gd_file in project.gd_files:
            assert gd_file.is_absolute()

    def test_empty_project_returns_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / "project.godot").touch()
        project = discover_project(tmp_path)
        assert project.gd_files == []
        assert project.project_root == tmp_path.resolve()


class TestExcludeDirs:
    """Tests for the exclude_dirs parameter of discover_project."""

    def _make_project(self, tmp_path: Path, dirs_and_files: dict[str, list[str]]) -> Path:
        """Create a synthetic Godot project with given directory structure.

        dirs_and_files maps directory paths (relative to project root) to
        lists of .gd filenames to create in that directory.  An empty string
        key means the project root.
        """
        (tmp_path / "project.godot").touch()
        for dir_path, filenames in dirs_and_files.items():
            d = tmp_path / dir_path if dir_path else tmp_path
            d.mkdir(parents=True, exist_ok=True)
            for fname in filenames:
                (d / fname).write_text(f"# {fname}\n", encoding="utf-8")
        return tmp_path

    def test_no_excludes_finds_all(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "src": ["game.gd"],
            "addons": ["plugin.gd"],
            "test": ["test_game.gd"],
        })
        project = discover_project(root)
        assert len(project.gd_files) == 4

    def test_exclude_single_dir(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "src": ["game.gd"],
            "addons": ["plugin.gd"],
            "test": ["test_game.gd"],
        })
        project = discover_project(root, exclude_dirs=["addons"])
        filenames = {p.name for p in project.gd_files}

        assert "plugin.gd" not in filenames
        assert "main.gd" in filenames
        assert "game.gd" in filenames
        assert "test_game.gd" in filenames

    def test_exclude_multiple_dirs(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "src": ["game.gd"],
            "addons": ["plugin.gd"],
            "test": ["test_game.gd"],
        })
        project = discover_project(root, exclude_dirs=["addons", "test"])
        filenames = {p.name for p in project.gd_files}

        assert filenames == {"main.gd", "game.gd"}

    def test_exclude_nested_dir(self, tmp_path: Path) -> None:
        """Exclusion applies at any depth in the path."""
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "addons/gut": ["gut.gd"],
            "addons/gut/lib": ["util.gd"],
        })
        project = discover_project(root, exclude_dirs=["addons"])
        filenames = {p.name for p in project.gd_files}

        assert filenames == {"main.gd"}

    def test_godot_dir_always_excluded(self, tmp_path: Path) -> None:
        """The .godot directory is excluded even without explicit exclude_dirs."""
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            ".godot": ["cache.gd"],
        })
        project = discover_project(root, exclude_dirs=["test"])
        filenames = {p.name for p in project.gd_files}

        assert "cache.gd" not in filenames
        assert "main.gd" in filenames

    def test_exclude_none_same_as_no_exclude(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "addons": ["plugin.gd"],
        })
        without = discover_project(root, exclude_dirs=None)
        default = discover_project(root)

        assert len(without.gd_files) == len(default.gd_files)

    def test_exclude_empty_list_same_as_no_exclude(self, tmp_path: Path) -> None:
        root = self._make_project(tmp_path, {
            "": ["main.gd"],
            "addons": ["plugin.gd"],
        })
        project = discover_project(root, exclude_dirs=[])
        assert len(project.gd_files) == 2

    def test_existing_fixtures_exclude_actors(self, fixtures_dir: Path) -> None:
        """Excluding 'actors' from the real fixtures drops character, player, enemy."""
        project = discover_project(fixtures_dir, exclude_dirs=["actors"])
        filenames = {p.name for p in project.gd_files}

        assert "character.gd" not in filenames
        assert "player.gd" not in filenames
        assert "enemy.gd" not in filenames
        assert "bullet.gd" in filenames
        assert "helpers.gd" in filenames

    def test_existing_fixtures_exclude_weapons_and_utils(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir, exclude_dirs=["weapons", "utils"])
        filenames = {p.name for p in project.gd_files}

        assert "bullet.gd" not in filenames
        assert "helpers.gd" not in filenames
        assert "character.gd" in filenames
        assert "player.gd" in filenames


class TestToResPath:
    def test_converts_absolute_path_to_res_path(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        player_path = next(
            p for p in project.gd_files if p.name == "player.gd"
        )
        res_path = project.to_res_path(player_path)
        assert res_path == "res://actors/player.gd"

    def test_converts_root_level_file(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        empty_path = next(
            p for p in project.gd_files if p.name == "empty_file.gd"
        )
        res_path = project.to_res_path(empty_path)
        assert res_path == "res://empty_file.gd"

    def test_converts_nested_path(self, fixtures_dir: Path) -> None:
        project = discover_project(fixtures_dir)
        helpers_path = next(
            p for p in project.gd_files if p.name == "helpers.gd"
        )
        res_path = project.to_res_path(helpers_path)
        assert res_path == "res://utils/helpers.gd"
