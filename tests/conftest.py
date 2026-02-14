import pytest
from pathlib import Path

from gdscript_code_graph.discovery import ProjectFiles, discover_project


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return (Path(__file__).parent / "fixtures").resolve()


@pytest.fixture(scope="session")
def fixture_project(fixtures_dir: Path) -> ProjectFiles:
    return discover_project(fixtures_dir)
