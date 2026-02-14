from __future__ import annotations

__version__ = "1.0.0"

from .discovery import ProjectFiles, discover_project
from .graph import build_graph, serialize_graph
from .schema import Evidence, FunctionMetrics, Graph, GraphLink, GraphNode, Meta, NodeMetrics

__all__ = [
    "ProjectFiles",
    "discover_project",
    "build_graph",
    "serialize_graph",
    "Evidence",
    "FunctionMetrics",
    "Graph",
    "GraphLink",
    "GraphNode",
    "Meta",
    "NodeMetrics",
]
