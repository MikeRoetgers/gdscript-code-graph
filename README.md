# gdscript-code-graph

[![CI](https://github.com/MikeRoetgers/gdscript-code-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/MikeRoetgers/gdscript-code-graph/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/gdscript-code-graph.svg)](https://pypi.org/project/gdscript-code-graph/)
[![Python versions](https://img.shields.io/pypi/pyversions/gdscript-code-graph.svg)](https://pypi.org/project/gdscript-code-graph/)
[![license](https://img.shields.io/pypi/l/gdscript-code-graph)](https://github.com/MikeRoetgers/gdscript-code-graph/blob/main/LICENSE.md)

CLI tool that statically analyzes GDScript (Godot Engine) projects and outputs a structured JSON graph of files, code metrics, and inter-file relationships.

## Installation

Requires Python 3.10+.

```bash
pip install gdscript-code-graph
```

## Usage

```bash
# Analyze a Godot project (output to stdout)
gdscript-code-graph analyze <project-dir>

# Write output to a file
gdscript-code-graph analyze <project-dir> -o graph.json

# Custom repo name and directory exclusions
gdscript-code-graph analyze <project-dir> -o graph.json --repo-name my-game -e addons -e test
```

### Options

| Flag | Description |
|---|---|
| `-o`, `--out` | Output file path (default: stdout) |
| `--repo-name` | Repository name in output (default: directory name) |
| `-e`, `--exclude` | Directory names to exclude (repeatable) |

## Output

The output format is documented in [simple-code-graph-viewer/docs/schema.md](https://github.com/MikeRoetgers/simple-code-graph-viewer/blob/main/docs/schema.md).