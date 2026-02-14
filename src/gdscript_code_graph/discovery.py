from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectFiles:
    project_root: Path          # directory containing project.godot
    gd_files: list[Path]        # absolute paths to all .gd files

    def to_res_path(self, abs_path: Path) -> str:
        rel = abs_path.relative_to(self.project_root)
        return "res://" + rel.as_posix()


def find_project_root(start_dir: Path) -> Path:
    """Check start_dir / "project.godot". If not found, walk upward.

    Raise FileNotFoundError if no project.godot is found anywhere.
    """
    current = start_dir.resolve()
    while True:
        if (current / "project.godot").exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                f"No project.godot found in {start_dir} or any parent directory"
            )
        current = parent


def discover_project(
    project_dir: Path,
    exclude_dirs: list[str] | None = None,
) -> ProjectFiles:
    """Call find_project_root, then glob ``**/*.gd`` under the project root.

    Always excludes the ``.godot/`` directory (Godot internal cache).
    Additional directories can be excluded via *exclude_dirs* -- each entry
    is matched against every component of the file's path relative to the
    project root.  For example, ``exclude_dirs=["addons", "test"]`` will
    skip any ``.gd`` file whose relative path contains an ``addons`` or
    ``test`` directory component.

    Sort files for deterministic output.
    Return empty list (not error) if zero ``.gd`` files found.
    """
    root = find_project_root(project_dir)

    # Always exclude .godot; merge user-supplied directories.
    always_excluded = {".godot"}
    if exclude_dirs:
        always_excluded.update(exclude_dirs)

    gd_files = sorted(
        resolved
        for p in root.rglob("*.gd")
        if not always_excluded.intersection(
            (resolved := p.resolve()).relative_to(root).parts
        )
    )
    return ProjectFiles(project_root=root, gd_files=gd_files)
