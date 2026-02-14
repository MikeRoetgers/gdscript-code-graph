from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from lark import Tree, Token

from gdscript_code_graph.schema import FunctionMetrics


@dataclass
class FileMetrics:
    loc: int
    max_cc: int | None
    median_cc: float | None
    mi: float | None
    mi_min: float | None
    mi_median: float | None
    functions: list[FunctionMetrics]


@dataclass
class HalsteadResult:
    volume: float       # N * log2(n)
    vocabulary: int     # n = unique operators + unique operands
    length: int         # N = total operators + total operands


# ---------------------------------------------------------------------------
# Halstead classification tables
# ---------------------------------------------------------------------------

# Token types that count as operators (explicit named tokens).
_OPERATOR_TOKEN_TYPES = frozenset({
    "DOT", "EQUAL", "MINUS", "PLUS", "STAR", "SLASH", "PERCENT",
    "MORETHAN", "LESSTHAN",
    "AND", "OR", "NOT",
    "IF", "ELSE",
})

# Token types that count as operands.
_OPERAND_TOKEN_TYPES = frozenset({
    "NAME", "NUMBER", "REGULAR_STRING", "TYPE_HINT",
})

# Subtree node types that represent keyword operators absorbed by the grammar.
# Each occurrence contributes exactly one keyword operator.  Only *wrapper*
# nodes are listed (not inner variants like class_var_typed_assgnd) to
# avoid double-counting.
_KEYWORD_SUBTREE_MAP: dict[str, str] = {
    "extends_stmt": "extends",
    "classname_stmt": "class_name",
    "func_def": "func",
    "class_var_stmt": "var",
    "func_var_stmt": "var",
    "const_stmt": "const",
    "if_branch": "if",
    "elif_branch": "elif",
    "else_branch": "else",
    "for_stmt": "for",
    "for_stmt_typed": "for",
    "while_stmt": "while",
    "match_stmt": "match",
    "pass_stmt": "pass",
    "return_stmt": "return",
    "signal_stmt": "signal",
}


# ---------------------------------------------------------------------------
# LOC
# ---------------------------------------------------------------------------


def compute_loc(source: str) -> int:
    """Count non-empty, non-comment-only lines."""
    return sum(
        1 for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


# ---------------------------------------------------------------------------
# Cyclomatic complexity
# ---------------------------------------------------------------------------


def compute_cyclomatic_complexity(tree: Tree) -> int:
    """Compute cyclomatic complexity from a Lark AST.

    CC = 1 (base) plus count of branching constructs:
      - if_branch, elif_branch, while_stmt, for_stmt, for_stmt_typed, match_branch
      - and/&& tokens in and_test / asless_and_test nodes
      - or/|| tokens in or_test / asless_or_test nodes
      - ternary "if" tokens in test_expr / asless_test_expr nodes
    """
    cc = 1

    for subtree in tree.iter_subtrees():
        node_type = subtree.data

        # Direct branch nodes: +1 each
        if node_type in (
            "if_branch",
            "elif_branch",
            "while_stmt",
            "for_stmt",
            "for_stmt_typed",
            "match_branch",
        ):
            cc += 1

        # Boolean operators in and_test / asless_and_test:
        # "and" has token type AND, "&&" has token type __ANON_3
        if node_type in ("and_test", "asless_and_test"):
            for child in subtree.children:
                if isinstance(child, Token) and child.type in ("AND", "__ANON_3"):
                    cc += 1

        # Boolean operators in or_test / asless_or_test:
        # "or" has token type OR, "||" has token type __ANON_2
        if node_type in ("or_test", "asless_or_test"):
            for child in subtree.children:
                if isinstance(child, Token) and child.type in ("OR", "__ANON_2"):
                    cc += 1

        # Ternary expressions: test_expr / asless_test_expr with "if" token
        if node_type in ("test_expr", "asless_test_expr"):
            for child in subtree.children:
                if isinstance(child, Token) and child.type == "IF":
                    cc += 1

    return cc


def _extract_func_name(func_def: Tree) -> str:
    """Extract function name from a func_def subtree.

    Looks for the ``func_header`` child and returns the first ``NAME`` token.
    Returns ``"<unknown>"`` if no name is found.
    """
    for child in func_def.children:
        if isinstance(child, Tree) and child.data == "func_header":
            for header_child in child.children:
                if isinstance(header_child, Token) and header_child.type == "NAME":
                    return str(header_child)
            break
    return "<unknown>"


def compute_function_loc(source: str, start_line: int, end_line: int) -> int:
    """Count non-empty, non-comment lines within a function's source range.

    ``start_line`` and ``end_line`` are 1-based line numbers from Lark AST
    metadata.  Lark's ``end_line`` points past the last code line of the
    function (it includes trailing ``_NL`` tokens), so ``end_line - 1``
    is always >= the last code line, making the slice inclusive of all
    function lines.

    Extracts lines ``[start_line-1 : end_line-1]`` and applies the same
    counting logic as :func:`compute_loc`.
    """
    # Verified: Lark's meta.end_line accounts for trailing _NL tokens,
    # so end_line - 1 correctly includes the last code line of the function.
    lines = source.splitlines()
    func_lines = lines[start_line - 1 : end_line - 1]
    return sum(
        1 for line in func_lines
        if line.strip() and not line.strip().startswith("#")
    )


def compute_function_metrics(
    func_def: Tree, source: str
) -> FunctionMetrics:
    """Compute all metrics for a single function.

    Extracts name, line number, CC, LOC, Halstead volume, and MI from
    the ``func_def`` subtree and its corresponding source lines.

    Returns a :class:`FunctionMetrics` with ``mi=None`` if LOC=0 or
    Halstead volume=0.
    """
    name = _extract_func_name(func_def)
    line = func_def.meta.line
    end_line = func_def.meta.end_line

    cc = compute_cyclomatic_complexity(func_def)
    loc = compute_function_loc(source, line, end_line)
    halstead = compute_halstead_volume(func_def)

    mi: float | None = None
    if loc > 0 and halstead.volume > 0:
        mi = compute_maintainability_index(loc, cc, halstead.volume)

    return FunctionMetrics(name=name, line=line, cc=cc, loc=loc, mi=mi)


def compute_all_function_metrics(
    tree: Tree, source: str
) -> list[FunctionMetrics]:
    """Compute metrics for every function in a Lark AST.

    Walks the tree to find ``func_def`` subtrees.  For each, calls
    :func:`compute_function_metrics` to get name, line, CC, LOC, and MI.

    Returns a list of :class:`FunctionMetrics` — one per function in source
    order.  Files with no functions return an empty list.
    """
    results: list[FunctionMetrics] = []

    for subtree in tree.iter_subtrees():
        if subtree.data != "func_def":
            continue
        results.append(compute_function_metrics(subtree, source))

    return results


def aggregate_cc(
    per_func: list[FunctionMetrics],
) -> tuple[int, float]:
    """Aggregate per-function CC into max and median.

    Returns ``(max_cc, median_cc)``.

    - ``max_cc``: the highest CC among all functions (hotspot detection).
    - ``median_cc``: the median CC across all functions (typical complexity),
      rounded to 1 decimal place.

    If the list is empty (no functions in the file), returns ``(1, 1.0)``
    as a baseline — any executable code path has a minimum CC of 1.
    """
    if not per_func:
        return (1, 1.0)

    cc_values = [f.cc for f in per_func]
    max_cc = max(cc_values)
    median_cc = round(float(statistics.median(cc_values)), 1)
    return (max_cc, median_cc)


def aggregate_mi(
    per_func: list[FunctionMetrics],
) -> tuple[float | None, float | None]:
    """Aggregate per-function MI into min and median.

    Returns ``(mi_min, mi_median)``.

    - ``mi_min``: the lowest MI among all functions (worst maintainability).
    - ``mi_median``: the median MI across all functions, rounded to 2 decimals.

    Returns ``(None, None)`` if no functions have a non-None MI value.
    """
    mi_values = [f.mi for f in per_func if f.mi is not None]
    if not mi_values:
        return (None, None)

    mi_min = min(mi_values)
    mi_median = round(float(statistics.median(mi_values)), 2)
    return (mi_min, mi_median)


# ---------------------------------------------------------------------------
# Halstead volume
# ---------------------------------------------------------------------------


def compute_halstead_volume(tree: Tree) -> HalsteadResult:
    """Compute Halstead volume from a Lark AST.

    Walks the tree once, classifying Token leaves and subtree types
    into operators and operands.

    Operator tokens: named types (DOT, EQUAL, PLUS, …) plus any __ANON_*
    tokens (compound assignment, comparisons, &&, ||, etc.).

    Operand tokens: NAME, NUMBER, REGULAR_STRING, TYPE_HINT.

    Keyword operators (absorbed by the grammar): recovered from subtree
    node types like extends_stmt → "extends", func_def → "func", etc.

    Returns a HalsteadResult with volume (N × log₂(n)), vocabulary (n),
    and program length (N).
    """
    operators: list[str] = []
    operands: list[str] = []

    for subtree in tree.iter_subtrees():
        # Recover keyword operators from subtree types
        keyword = _KEYWORD_SUBTREE_MAP.get(str(subtree.data))
        if keyword is not None:
            operators.append(keyword)

        # Classify Token leaves
        for child in subtree.children:
            if not isinstance(child, Token):
                continue
            if child.type in _OPERATOR_TOKEN_TYPES:
                operators.append(str(child))
            elif child.type in _OPERAND_TOKEN_TYPES:
                operands.append(str(child))
            elif child.type.startswith("__ANON"):
                operators.append(str(child))

    n1 = len(set(operators))    # unique operators
    n2 = len(set(operands))     # unique operands
    n = n1 + n2                 # vocabulary
    big_n = len(operators) + len(operands)  # program length

    volume = big_n * math.log2(n) if n > 0 else 0.0

    return HalsteadResult(volume=volume, vocabulary=n, length=big_n)


# ---------------------------------------------------------------------------
# Maintainability index
# ---------------------------------------------------------------------------


def compute_maintainability_index(
    loc: int, cc: int, halstead_volume: float
) -> float:
    """Compute Maintainability Index from LOC, CC, and Halstead Volume.

    Uses the standard MI formula (0–171 scale):
        MI = 171 − 5.2 × ln(V) − 0.23 × CC − 16.2 × ln(LOC)

    Result is clamped to a minimum of 0.

    Requires ``loc > 0`` and ``halstead_volume > 0`` (both are arguments
    to ``math.log``).  Raises ``ValueError`` if either is <= 0.
    """
    if loc <= 0:
        raise ValueError(f"loc must be > 0, got {loc}")
    if halstead_volume <= 0:
        raise ValueError(f"halstead_volume must be > 0, got {halstead_volume}")
    mi = (
        171
        - 5.2 * math.log(halstead_volume)
        - 0.23 * cc
        - 16.2 * math.log(loc)
    )
    return round(max(0.0, mi), 2)


# ---------------------------------------------------------------------------
# Aggregate entry point
# ---------------------------------------------------------------------------


def compute_metrics(source: str, tree: Tree | None) -> FileMetrics:
    """Compute all metrics for a single file.

    LOC is always computed from raw source text.
    Per-function metrics (CC, LOC, MI) are computed from the AST if available.
    CC is aggregated into max_cc and median_cc.  Both are None if parse failed.
    File-level MI is computed when tree is available, max_cc is known, LOC > 0,
    and whole-file Halstead volume > 0.  MI uses max_cc in its formula.
    Per-function MI is aggregated into mi_min and mi_median.
    """
    loc = compute_loc(source)

    max_cc: int | None = None
    median_cc: float | None = None
    mi: float | None = None
    mi_min: float | None = None
    mi_median: float | None = None
    functions: list[FunctionMetrics] = []

    if tree is not None:
        functions = compute_all_function_metrics(tree, source)
        max_cc, median_cc = aggregate_cc(functions)
        mi_min, mi_median = aggregate_mi(functions)

    # File-level MI uses max_cc (worst per-function CC) rather than the
    # standard total-file CC.  This penalises files containing a single
    # highly complex function instead of diluting the score across many
    # simple functions.  Per-function MI (mi_min, mi_median) already
    # uses each function's own CC for granular analysis.
    if tree is not None and max_cc is not None and loc > 0:
        halstead = compute_halstead_volume(tree)
        if halstead.volume > 0:
            mi = compute_maintainability_index(loc, max_cc, halstead.volume)

    return FileMetrics(
        loc=loc,
        max_cc=max_cc,
        median_cc=median_cc,
        mi=mi,
        mi_min=mi_min,
        mi_median=mi_median,
        functions=functions,
    )
