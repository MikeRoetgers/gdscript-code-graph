from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from lark import Tree, Token

from gdscript_code_graph.parsing import ParseResult
from gdscript_code_graph.schema import Evidence, GraphLink

logger = logging.getLogger(__name__)

_ARRAY_TYPE_RE = re.compile(r"Array\[(\w+)\]")


@dataclass
class RawRelationship:
    source_res_path: str
    target: str             # res:// path OR class name
    kind: str               # "extends", "preloads", "loads"
    line: int


def _extract_string_value(string_tree: Tree) -> str:
    """Extract the unquoted string value from a Lark ``string`` tree node.

    The ``string`` node has a single child token of type ``REGULAR_STRING``
    (e.g. ``"res://actors/character.gd"``).  We strip the surrounding
    double-quotes to return the raw path.
    """
    token = str(string_tree.children[0])
    if len(token) >= 2 and token[0] in ('"', "'") and token[-1] == token[0]:
        return token[1:-1]
    return token


def extract_class_name(tree: Tree) -> str | None:
    """Return the declared ``class_name`` from a parsed GDScript AST, or None.

    Handles both ``classname_stmt`` (e.g. ``class_name Player``) and
    ``classname_extends_stmt`` (e.g. ``class_name Foo extends Bar``) forms.
    In the latter case the *first* ``NAME`` token is the class name.
    """
    for subtree in tree.iter_subtrees():
        if subtree.data == "classname_stmt":
            for child in subtree.children:
                if isinstance(child, Token) and child.type == "NAME":
                    return str(child)
        if subtree.data == "classname_extends_stmt":
            for child in subtree.children:
                if isinstance(child, Token) and child.type == "NAME":
                    return str(child)
    return None


def extract_extends(tree: Tree, source_res_path: str) -> list[RawRelationship]:
    """Extract ``extends`` relationships from a parsed GDScript AST.

    Handles three forms:
    - ``extends ClassName`` -- extends by class name (NAME token)
    - ``extends "res://path.gd"`` -- extends by path (string subtree)
    - ``class_name Foo extends Bar`` -- classname_extends_stmt (second NAME
      token after the class name is the extends target)
    """
    results: list[RawRelationship] = []

    for subtree in tree.iter_subtrees():
        if subtree.data == "extends_stmt":
            line = getattr(subtree.meta, "line", 0)
            for child in subtree.children:
                if isinstance(child, Tree) and child.data == "string":
                    # extends "res://path/to/file.gd"
                    target = _extract_string_value(child)
                    results.append(RawRelationship(
                        source_res_path=source_res_path,
                        target=target,
                        kind="extends",
                        line=line,
                    ))
                elif isinstance(child, Token) and child.type == "NAME":
                    # extends ClassName
                    results.append(RawRelationship(
                        source_res_path=source_res_path,
                        target=str(child),
                        kind="extends",
                        line=line,
                    ))

        elif subtree.data == "classname_extends_stmt":
            line = getattr(subtree.meta, "line", 0)
            # Children are NAME tokens; the first is the class_name, the
            # second (after the implicit ``extends`` keyword) is the target.
            name_tokens = [
                child for child in subtree.children
                if isinstance(child, Token) and child.type == "NAME"
            ]
            if len(name_tokens) >= 2:
                target = str(name_tokens[1])
                results.append(RawRelationship(
                    source_res_path=source_res_path,
                    target=target,
                    kind="extends",
                    line=line,
                ))

    return results


def extract_preloads(tree: Tree, source_res_path: str) -> list[RawRelationship]:
    """Extract ``preload(...)`` and ``load(...)`` relationships from an AST.

    Walks the tree looking for:

    1. ``standalone_call`` nodes whose first child is a ``NAME`` token equal
       to ``preload`` or ``load`` (bare calls like ``preload("res://...")``).
    2. ``getattr_call`` nodes where the ``getattr`` subtree ends with a
       ``NAME`` token equal to ``load`` (e.g. ``ResourceLoader.load("res://...")``).
       Only ``load`` is handled here -- ``preload`` is a GDScript keyword and
       is never called via attribute access.

    If the call has a ``string`` argument that starts with ``res://``, it is
    recorded.
    """
    results: list[RawRelationship] = []

    for subtree in tree.iter_subtrees():
        if subtree.data == "standalone_call":
            children = subtree.children
            if not children:
                continue

            first = children[0]
            if not (isinstance(first, Token) and first.type == "NAME"):
                continue

            func_name = str(first)
            if func_name not in ("preload", "load"):
                continue

            kind = func_name + "s"  # "preloads" or "loads"
            line = getattr(subtree.meta, "line", 0)

            # Look for string argument among remaining children
            for child in children[1:]:
                if isinstance(child, Tree) and child.data == "string":
                    target = _extract_string_value(child)
                    if target.startswith("res://"):
                        results.append(RawRelationship(
                            source_res_path=source_res_path,
                            target=target,
                            kind=kind,
                            line=line,
                        ))

        elif subtree.data == "getattr_call":
            children = subtree.children
            if not children:
                continue

            # First child should be a ``getattr`` subtree.
            first = children[0]
            if not (isinstance(first, Tree) and first.data == "getattr"):
                continue

            # The last NAME token in the getattr chain is the method name.
            name_tokens = [
                child for child in first.children
                if isinstance(child, Token) and child.type == "NAME"
            ]
            if not name_tokens or str(name_tokens[-1]) != "load":
                continue

            line = getattr(subtree.meta, "line", 0)

            # Look for string arguments among remaining children
            for child in children[1:]:
                if isinstance(child, Tree) and child.data == "string":
                    target = _extract_string_value(child)
                    if target.startswith("res://"):
                        results.append(RawRelationship(
                            source_res_path=source_res_path,
                            target=target,
                            kind="loads",
                            line=line,
                        ))

    return results


def extract_type_from_hint(type_hint: str) -> str:
    """Extract the inner type name from a TYPE_HINT token value.

    Handles ``Array[Type]`` by returning the inner type (``Type``).
    For plain types like ``Player`` returns the value as-is.

    Examples::

        >>> extract_type_from_hint("Player")
        'Player'
        >>> extract_type_from_hint("Array[Item]")
        'Item'
        >>> extract_type_from_hint("Array")
        'Array'
    """
    match = _ARRAY_TYPE_RE.match(type_hint)
    if match:
        return match.group(1)
    return type_hint


def extract_typed_deps(
    tree: Tree, source_res_path: str
) -> list[RawRelationship]:
    """Extract typed-dependency relationships from class variable declarations.

    Detects patterns:

    - ``var x: Type`` (``class_var_typed`` AST node)
    - ``var x: Type = value`` (``class_var_typed_assgnd`` AST node)
    - ``var x: Array[Type]`` / ``var x: Array[Type] = []``

    Each produces a ``RawRelationship`` with ``kind="typed_dependency"``
    where the target is the type name (or inner type for ``Array[Type]``).
    Built-in types are *not* filtered here -- that happens during resolution
    when the type name is looked up in the class-name table.
    """
    results: list[RawRelationship] = []

    for subtree in tree.iter_subtrees():
        if subtree.data not in ("class_var_typed", "class_var_typed_assgnd"):
            continue

        type_hint: str | None = None
        for child in subtree.children:
            if isinstance(child, Token) and child.type == "TYPE_HINT":
                type_hint = str(child)
                break

        if type_hint is None:
            continue

        target = extract_type_from_hint(type_hint)
        line = getattr(subtree.meta, "line", 0)
        results.append(RawRelationship(
            source_res_path=source_res_path,
            target=target,
            kind="typed_dependency",
            line=line,
        ))

    return results


def extract_returns(
    tree: Tree, source_res_path: str
) -> list[RawRelationship]:
    """Extract return-type relationships from function declarations.

    Detects ``func foo() -> Type:`` patterns by inspecting ``func_header``
    AST nodes for a ``TYPE_HINT`` token (which represents the return type).

    Each produces a ``RawRelationship`` with ``kind="returns"`` where the
    target is the type name (or inner type for ``Array[Type]``).  Built-in
    types are *not* filtered here -- that happens during resolution.
    """
    results: list[RawRelationship] = []

    for subtree in tree.iter_subtrees():
        if subtree.data != "func_header":
            continue

        # The return type is the last TYPE_HINT token that is a direct child of
        # func_header.  Parameter type hints live inside func_args (a Tree child),
        # so they are not visited here.  We iterate in reverse to grab the return
        # type first and break immediately.
        return_type: str | None = None
        for child in reversed(subtree.children):
            if isinstance(child, Token) and child.type == "TYPE_HINT":
                return_type = str(child)
                break

        if return_type is None:
            continue

        target = extract_type_from_hint(return_type)
        line = getattr(subtree.meta, "line", 0)
        results.append(RawRelationship(
            source_res_path=source_res_path,
            target=target,
            kind="returns",
            line=line,
        ))

    return results


def build_class_name_table(
    parse_results: list[ParseResult],
) -> dict[str, str]:
    """Build a mapping of class_name declarations to their ``res://`` paths.

    Iterates over all successfully parsed files and extracts any
    ``class_name`` declaration.  If two files declare the same class name
    a warning is logged and the later entry wins.
    """
    table: dict[str, str] = {}

    for pr in parse_results:
        if pr.tree is None:
            continue
        name = extract_class_name(pr.tree)
        if name is None:
            continue
        if name in table:
            logger.warning(
                "Duplicate class_name %r: %s and %s",
                name,
                table[name],
                pr.res_path,
            )
        table[name] = pr.res_path

    return table


def _resolve_target(
    rel: RawRelationship,
    class_name_table: dict[str, str],
    known_res_paths: set[str],
) -> str | None:
    """Resolve a single relationship target to a ``res://`` path, or None.

    - If the target already starts with ``res://``, it is returned directly --
      but only if it appears in *known_res_paths*.
    - If the target is a class name, it is looked up in *class_name_table*.
    - Returns ``None`` if the target cannot be resolved (built-in class,
      unknown path).
    """
    if rel.target.startswith("res://"):
        if rel.target not in known_res_paths:
            return None
        return rel.target
    target_path = class_name_table.get(rel.target)
    return target_path  # None if built-in / unknown


def resolve_relationships_with_evidence(
    raw_rels: list[RawRelationship],
    class_name_table: dict[str, str],
    known_res_paths: set[str],
) -> list[GraphLink]:
    """Resolve raw relationships to ``GraphLink`` objects with evidence.

    Collects **all** occurrences of each ``(source, target, kind)`` tuple
    into an ``evidence`` array and sets ``weight`` to the occurrence count.

    - If the target already starts with ``res://``, it is used directly --
      but only if it appears in *known_res_paths* (i.e. it actually exists
      in the project).
    - If the target is a class name, it is looked up in *class_name_table*.
      If found, the corresponding ``res://`` path is used.  If not found,
      the target is assumed to be a built-in Godot class and the
      relationship is **skipped**.

    Returns a sorted list of ``GraphLink`` objects (sorted by
    ``(source, target, kind)`` for deterministic output).
    """
    evidence_map: dict[tuple[str, str, str], list[Evidence]] = defaultdict(list)

    for rel in raw_rels:
        target_path = _resolve_target(rel, class_name_table, known_res_paths)
        if target_path is None:
            continue

        key = (rel.source_res_path, target_path, rel.kind)
        evidence_map[key].append(Evidence(
            file=rel.source_res_path,
            line=rel.line,
        ))

    return [
        GraphLink(
            source=source,
            target=target,
            kind=kind,
            weight=len(evidence_list),
            evidence=evidence_list,
        )
        for (source, target, kind), evidence_list in sorted(evidence_map.items())
    ]
