from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from gdscript_code_graph.discovery import ProjectFiles
from gdscript_code_graph.metrics import compute_metrics
from gdscript_code_graph.parsing import parse_all
from gdscript_code_graph.relationships import (
    build_class_name_table,
    extract_extends,
    extract_preloads,
    extract_returns,
    extract_typed_deps,
    resolve_relationships_with_evidence,
)
from gdscript_code_graph.schema import (
    FunctionMetrics,
    Graph,
    GraphNode,
    Meta,
    NodeMetrics,
)


def build_graph(project: ProjectFiles, repo_name: str) -> Graph:
    """Run the full analysis pipeline and assemble a Graph.

    Pipeline:
    1. Parse all .gd files
    2. Build class name lookup table
    3. For each file: compute metrics, look up class_name, extract raw
       relationships, build node
    4. Resolve relationships with evidence (class names to paths, skip
       built-ins, aggregate evidence arrays)
    5. Assemble Graph with schema_version="1.0" and metadata
    """
    # Step 1: Parse
    parse_results = parse_all(project)

    # Step 2: Build class name table
    class_name_table = build_class_name_table(parse_results)
    res_path_to_class_name = {v: k for k, v in class_name_table.items()}

    # Step 3: Process each file
    nodes: list[GraphNode] = []
    all_raw_rels = []

    for pr in parse_results:
        # Compute metrics
        file_metrics = compute_metrics(pr.source, pr.tree)

        # Node name: class_name if declared, else filename stem
        name = res_path_to_class_name.get(pr.res_path) or Path(pr.file_path).stem

        # Build node
        node = GraphNode(
            id=pr.res_path,
            kind="script",
            language="gdscript",
            name=name,
            metrics=NodeMetrics(
                loc=file_metrics.loc,
                max_cc=file_metrics.max_cc,
                median_cc=file_metrics.median_cc,
                mi=file_metrics.mi,
                mi_min=file_metrics.mi_min,
                mi_median=file_metrics.mi_median,
                functions=file_metrics.functions,
            ),
            tags=[],
        )
        nodes.append(node)

        # Extract raw relationships (only if tree is valid)
        if pr.tree is not None:
            all_raw_rels.extend(extract_extends(pr.tree, pr.res_path))
            all_raw_rels.extend(extract_preloads(pr.tree, pr.res_path))
            all_raw_rels.extend(extract_typed_deps(pr.tree, pr.res_path))
            all_raw_rels.extend(extract_returns(pr.tree, pr.res_path))

    # Step 4: Resolve relationships and build GraphLinks with evidence
    known_res_paths = {pr.res_path for pr in parse_results}
    links = resolve_relationships_with_evidence(
        all_raw_rels, class_name_table, known_res_paths
    )

    # Step 5: Assemble Graph
    now = datetime.now(timezone.utc).isoformat()

    return Graph(
        schema_version="1.0",
        meta=Meta(repo=repo_name, generated_at=now),
        nodes=nodes,
        links=links,
    )


def serialize_graph(graph: Graph) -> str:
    """Serialize a Graph to a JSON string."""
    return json.dumps(asdict(graph), indent=2)
