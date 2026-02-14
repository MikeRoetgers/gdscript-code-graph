from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Evidence:
    file: str           # res:// path where the relationship was found
    line: int           # line number


@dataclass
class FunctionMetrics:
    name: str               # function name
    line: int               # start line number
    cc: int                 # cyclomatic complexity
    loc: int                # non-empty, non-comment lines in this function
    mi: float | None        # maintainability index (None if loc=0 or volume=0)


@dataclass
class NodeMetrics:
    loc: int                    # non-empty, non-comment lines
    max_cc: int | None          # max per-function cyclomatic complexity (None if parse failed)
    median_cc: float | None     # median per-function cyclomatic complexity (None if parse failed)
    mi: float | None = None     # file-level maintainability index (None if parse failed or empty file)
    mi_min: float | None = None     # worst per-function MI (None if no functions have MI)
    mi_median: float | None = None  # median per-function MI (None if no functions have MI)
    functions: list[FunctionMetrics] = field(default_factory=list)  # per-function detail


@dataclass
class GraphNode:
    id: str             # res:// path (stable identifier)
    kind: str           # "script" for v1
    language: str       # "gdscript" for v1
    name: str           # class_name if declared, else filename stem
    metrics: NodeMetrics
    tags: list[str] = field(default_factory=list)


@dataclass
class GraphLink:
    source: str         # res:// path
    target: str         # res:// path
    kind: str           # "extends", "preloads", "loads", "typed_dependency", "returns"
    weight: int         # number of occurrences
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Meta:
    repo: str
    generated_at: str   # ISO 8601


@dataclass
class Graph:
    schema_version: str
    meta: Meta
    nodes: list[GraphNode]
    links: list[GraphLink]
