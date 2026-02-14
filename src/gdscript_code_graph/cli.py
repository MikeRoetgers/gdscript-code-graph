from __future__ import annotations

import sys
from pathlib import Path

import click

from .discovery import discover_project
from .graph import build_graph, serialize_graph


@click.group()
def main():
    """GDScript code metrics analyzer."""
    pass


@main.command()
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--out",
    "-o",
    type=click.Path(),
    default=None,
    help="Output file path. Defaults to stdout.",
)
@click.option(
    "--repo-name",
    type=str,
    default=None,
    help="Repository name for the output. Defaults to directory name.",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Directory names to exclude (repeatable). Example: --exclude addons --exclude test",
)
def analyze(
    project_dir: str,
    out: str | None,
    repo_name: str | None,
    exclude: tuple[str, ...],
) -> None:
    """Analyze a Godot project directory for code metrics."""
    project_path = Path(project_dir)

    if repo_name is None:
        repo_name = project_path.name

    try:
        project = discover_project(
            project_path,
            exclude_dirs=list(exclude) if exclude else None,
        )
    except FileNotFoundError:
        click.echo(
            f"Error: No project.godot found in or above '{project_dir}'",
            err=True,
        )
        sys.exit(1)

    graph = build_graph(project, repo_name)
    json_output = serialize_graph(graph)

    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output, encoding="utf-8")
    else:
        click.echo(json_output)
