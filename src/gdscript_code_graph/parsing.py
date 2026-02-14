from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from gdtoolkit.parser import parser as gdparser
from lark import Tree

from gdscript_code_graph.discovery import ProjectFiles

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    file_path: Path
    res_path: str
    tree: Tree | None       # None if parse failed
    source: str             # raw source text (always populated)
    error: str | None       # error message if parse failed


def parse_file(file_path: Path, res_path: str) -> ParseResult:
    """Parse a single GDScript file and return a ParseResult.

    Uses gdtoolkit's parser with gather_metadata=True to get .meta.line
    on AST nodes. Gracefully handles parse errors and encoding issues --
    a broken file never raises; the error is captured in the result.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        logger.warning("Failed to read %s: %s", file_path, exc)
        return ParseResult(
            file_path=file_path,
            res_path=res_path,
            tree=None,
            source="",
            error=str(exc),
        )

    try:
        tree = gdparser.parse(source, gather_metadata=True)
        return ParseResult(
            file_path=file_path,
            res_path=res_path,
            tree=tree,
            source=source,
            error=None,
        )
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", file_path, exc)
        return ParseResult(
            file_path=file_path,
            res_path=res_path,
            tree=None,
            source=source,
            error=str(exc),
        )


def parse_all(project: ProjectFiles) -> list[ParseResult]:
    """Parse all .gd files in the project.

    Never aborts the whole batch -- individual file errors are captured
    in each ParseResult.
    """
    results = []
    for file_path in project.gd_files:
        res_path = project.to_res_path(file_path)
        results.append(parse_file(file_path, res_path))
    return results
