from pathlib import Path

import pytest
from gdtoolkit.parser import parser as gdparser

from gdscript_code_graph.metrics import (
    FileMetrics,
    HalsteadResult,
    aggregate_cc,
    aggregate_mi,
    compute_all_function_metrics,
    compute_cyclomatic_complexity,
    compute_function_loc,
    compute_function_metrics,
    compute_halstead_volume,
    compute_loc,
    compute_maintainability_index,
    compute_metrics,
)
from gdscript_code_graph.schema import FunctionMetrics


# ---------------------------------------------------------------------------
# Helper to parse a fixture file
# ---------------------------------------------------------------------------

def _parse_fixture(fixtures_dir: Path, rel_path: str):
    """Parse a fixture file and return (source, tree) tuple."""
    file_path = fixtures_dir / rel_path
    source = file_path.read_text(encoding="utf-8")
    tree = gdparser.parse(source, gather_metadata=True)
    return source, tree


# ===========================================================================
# LOC Tests
# ===========================================================================


class TestComputeLoc:
    def test_empty_string(self) -> None:
        assert compute_loc("") == 0

    def test_comment_only(self) -> None:
        assert compute_loc("# just a comment\n") == 0

    def test_single_code_line(self) -> None:
        assert compute_loc("var x = 1\n") == 1

    def test_whitespace_only_lines_not_counted(self) -> None:
        assert compute_loc("   \n\t\n  \t  \n") == 0

    def test_mixed_content(self) -> None:
        source = "# comment\nvar x = 1\n\n# another comment\nvar y = 2\n"
        assert compute_loc(source) == 2

    def test_player_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "actors/player.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 17

    def test_character_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "actors/character.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 9

    def test_enemy_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "actors/enemy.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 6

    def test_helpers_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "utils/helpers.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 3

    def test_bullet_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "weapons/bullet.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 5

    def test_empty_file_gd_fixture(self, fixtures_dir: Path) -> None:
        source = (fixtures_dir / "empty_file.gd").read_text(encoding="utf-8")
        assert compute_loc(source) == 0

    def test_no_trailing_newline(self) -> None:
        assert compute_loc("var x = 1") == 1

    def test_inline_comment_still_counted(self) -> None:
        """A line with code followed by a comment is still a code line."""
        assert compute_loc("var x = 1 # inline comment\n") == 1


# ===========================================================================
# Cyclomatic Complexity Tests
# ===========================================================================


class TestComputeCyclomaticComplexity:
    def test_character_gd_cc(self, fixtures_dir: Path) -> None:
        """character.gd: 1 base + 1 if = 2."""
        _, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        assert compute_cyclomatic_complexity(tree) == 2

    def test_player_gd_cc(self, fixtures_dir: Path) -> None:
        """player.gd: 1 base + 1 if + 1 elif = 3."""
        _, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        assert compute_cyclomatic_complexity(tree) == 3

    def test_enemy_gd_cc(self, fixtures_dir: Path) -> None:
        """enemy.gd: 1 base + 1 for + 1 if = 3."""
        _, tree = _parse_fixture(fixtures_dir, "actors/enemy.gd")
        assert compute_cyclomatic_complexity(tree) == 3

    def test_helpers_gd_cc(self, fixtures_dir: Path) -> None:
        """helpers.gd: 1 base + 1 and = 2."""
        _, tree = _parse_fixture(fixtures_dir, "utils/helpers.gd")
        assert compute_cyclomatic_complexity(tree) == 2

    def test_bullet_gd_cc(self, fixtures_dir: Path) -> None:
        """bullet.gd: 1 base only = 1."""
        _, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        assert compute_cyclomatic_complexity(tree) == 1

    def test_empty_file_cc(self, fixtures_dir: Path) -> None:
        """empty_file.gd: 1 base only = 1."""
        _, tree = _parse_fixture(fixtures_dir, "empty_file.gd")
        assert compute_cyclomatic_complexity(tree) == 1

    def test_while_loop_counted(self) -> None:
        source = "func f():\n\twhile true:\n\t\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 2  # 1 base + 1 while

    def test_or_operator_counted(self) -> None:
        source = "func f():\n\treturn true or false\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 2  # 1 base + 1 or

    def test_and_operator_counted(self) -> None:
        source = "func f():\n\treturn true and false\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 2  # 1 base + 1 and

    def test_ternary_expression_counted(self) -> None:
        source = "func f():\n\tvar x = 1 if true else 0\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 2  # 1 base + 1 ternary

    def test_multiple_branches_accumulate(self) -> None:
        """Multiple branching constructs all contribute to CC."""
        source = (
            "func f():\n"
            "\tif a:\n"
            "\t\tpass\n"
            "\telif b:\n"
            "\t\tpass\n"
            "\tfor i in range(10):\n"
            "\t\tif c and d:\n"
            "\t\t\tpass\n"
        )
        tree = gdparser.parse(source, gather_metadata=True)
        # 1 base + 1 if + 1 elif + 1 for + 1 if + 1 and = 6
        assert compute_cyclomatic_complexity(tree) == 6

    def test_double_ampersand_counted(self) -> None:
        """C-style && operator should count as +1."""
        source = "func f():\n\tif true && false:\n\t\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 3  # 1 base + 1 if + 1 &&

    def test_double_pipe_counted(self) -> None:
        """C-style || operator should count as +1."""
        source = "func f():\n\tif true || false:\n\t\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 3  # 1 base + 1 if + 1 ||

    def test_match_branches_counted(self) -> None:
        """Each match branch should count as +1."""
        source = "func f(x):\n\tmatch x:\n\t\t1:\n\t\t\tpass\n\t\t2:\n\t\t\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 3  # 1 base + 2 match branches

    def test_typed_for_loop_counted(self) -> None:
        """Typed for loop (for i: int in ...) should count as +1."""
        source = "func f():\n\tfor i: int in range(10):\n\t\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 2  # 1 base + 1 for_stmt_typed

    def test_base_cc_is_one(self) -> None:
        """A function with no branching has CC=1."""
        source = "func f():\n\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        assert compute_cyclomatic_complexity(tree) == 1


# ===========================================================================
# Per-Function Metrics Tests
# ===========================================================================


class TestComputeAllFunctionMetrics:
    def test_player_gd_two_functions(self, fixtures_dir: Path) -> None:
        """player.gd has _process and shoot with full per-function metrics."""
        source, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_all_function_metrics(tree, source)
        by_name = {f.name: f for f in result}

        assert len(result) == 2

        proc = by_name["_process"]
        assert proc.cc == 3       # 1 base + 1 if + 1 elif
        assert proc.line == 10
        assert proc.loc == 7
        assert proc.mi is not None

        shoot = by_name["shoot"]
        assert shoot.cc == 1      # 1 base only
        assert shoot.line == 18
        assert shoot.loc == 4
        assert shoot.mi is not None

    def test_character_gd_two_functions(self, fixtures_dir: Path) -> None:
        """character.gd has take_damage and get_bullet."""
        source, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        result = compute_all_function_metrics(tree, source)
        by_name = {f.name: f for f in result}

        assert len(result) == 2

        td = by_name["take_damage"]
        assert td.cc == 2          # 1 base + 1 if
        assert td.line == 6
        assert td.loc == 4
        assert td.mi is not None

        gb = by_name["get_bullet"]
        assert gb.cc == 1           # 1 base only
        assert gb.line == 11
        assert gb.loc == 2
        assert gb.mi is not None

    def test_enemy_gd_one_function(self, fixtures_dir: Path) -> None:
        """enemy.gd has _process with full metrics."""
        source, tree = _parse_fixture(fixtures_dir, "actors/enemy.gd")
        result = compute_all_function_metrics(tree, source)

        assert len(result) == 1
        f = result[0]
        assert f.name == "_process"
        assert f.cc == 3            # 1 base + 1 for + 1 if
        assert f.line == 5
        assert f.loc == 4
        assert f.mi is not None

    def test_helpers_gd_one_function(self, fixtures_dir: Path) -> None:
        """helpers.gd has is_alive with full metrics."""
        source, tree = _parse_fixture(fixtures_dir, "utils/helpers.gd")
        result = compute_all_function_metrics(tree, source)

        assert len(result) == 1
        f = result[0]
        assert f.name == "is_alive"
        assert f.cc == 2            # 1 base + 1 and
        assert f.line == 3
        assert f.loc == 2
        assert f.mi is not None

    def test_bullet_gd_one_function(self, fixtures_dir: Path) -> None:
        """bullet.gd has _physics_process with full metrics."""
        source, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        result = compute_all_function_metrics(tree, source)

        assert len(result) == 1
        f = result[0]
        assert f.name == "_physics_process"
        assert f.cc == 1
        assert f.line == 6
        assert f.loc == 2
        assert f.mi is not None

    def test_empty_file_no_functions(self, fixtures_dir: Path) -> None:
        """empty_file.gd has no functions."""
        source, tree = _parse_fixture(fixtures_dir, "empty_file.gd")
        result = compute_all_function_metrics(tree, source)
        assert result == []

    def test_multi_function_inline(self) -> None:
        """Multiple functions with different complexities, LOCs, and MIs."""
        source = (
            "func simple():\n"
            "\tpass\n"
            "\n"
            "func complex_fn():\n"
            "\tif a:\n"
            "\t\tpass\n"
            "\telif b:\n"
            "\t\tpass\n"
            "\tfor i in range(10):\n"
            "\t\tif c and d:\n"
            "\t\t\tpass\n"
        )
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_all_function_metrics(tree, source)
        by_name = {f.name: f for f in result}

        assert len(result) == 2

        s = by_name["simple"]
        assert s.cc == 1
        assert s.loc == 2  # "func simple():" + "\tpass"

        c = by_name["complex_fn"]
        # 1 base + 1 if + 1 elif + 1 for + 1 if + 1 and = 6
        assert c.cc == 6
        assert c.loc == 8  # all lines in the function

        # complex function should have lower MI than simple
        assert s.mi is not None
        assert c.mi is not None
        assert c.mi < s.mi

    def test_returns_function_metrics_dataclass(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        result = compute_all_function_metrics(tree, source)
        assert all(isinstance(f, FunctionMetrics) for f in result)

    def test_function_mi_is_valid_range(self, fixtures_dir: Path) -> None:
        """Per-function MI should be in [0, 171] range."""
        source, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_all_function_metrics(tree, source)
        for f in result:
            if f.mi is not None:
                assert 0 <= f.mi <= 171, f"{f.name} MI out of range: {f.mi}"


# ===========================================================================
# compute_function_loc Boundary Tests
# ===========================================================================


class TestComputeFunctionLoc:
    def test_single_line_function(self) -> None:
        """Slice [0:2] gives two code lines: the func header and the pass."""
        source = "func f():\n\tpass\n"
        assert compute_function_loc(source, 1, 3) == 2

    def test_comment_lines_excluded(self) -> None:
        """Comment-only lines within the range are not counted."""
        source = "func f():\n\t# comment\n\tpass\n"
        assert compute_function_loc(source, 1, 4) == 2

    def test_range_with_only_comments(self) -> None:
        """A range containing only comments and blanks returns 0."""
        source = "# header\n# more\n\nfunc f():\n\tpass\n"
        assert compute_function_loc(source, 1, 4) == 0

    def test_start_equals_end(self) -> None:
        """When start_line == end_line the slice is empty, so LOC is 0."""
        source = "func f():\n\tpass\n"
        assert compute_function_loc(source, 2, 2) == 0

    def test_end_beyond_file(self) -> None:
        """When end_line exceeds file length, Python slice truncates gracefully."""
        source = "func f():\n\tpass\n"
        assert compute_function_loc(source, 1, 100) == 2

    def test_function_loc_includes_last_line(self) -> None:
        """Verify the last code line of a function is included in LOC count."""
        source = "func foo():\n\tvar x = 1\n\treturn x\n"
        tree = gdparser.parse(source, gather_metadata=True)
        funcs = compute_all_function_metrics(tree, source)
        assert len(funcs) == 1
        # Both `var x = 1` and `return x` are code lines
        assert funcs[0].loc == 3  # func header + 2 body lines


# ===========================================================================
# Aggregate CC Tests
# ===========================================================================


class TestAggregateCC:
    @staticmethod
    def _fm(name: str, cc: int) -> FunctionMetrics:
        """Helper to create a FunctionMetrics with just name and cc filled."""
        return FunctionMetrics(name=name, line=1, cc=cc, loc=1, mi=100.0)

    def test_single_function(self) -> None:
        result = aggregate_cc([self._fm("f", 5)])
        assert result == (5, 5.0)

    def test_multiple_functions(self) -> None:
        funcs = [self._fm("a", 1), self._fm("b", 3), self._fm("c", 7)]
        max_cc, median_cc = aggregate_cc(funcs)
        assert max_cc == 7
        assert median_cc == 3.0

    def test_empty_list_returns_baseline(self) -> None:
        assert aggregate_cc([]) == (1, 1.0)

    def test_even_number_median(self) -> None:
        """Median of even count is average of middle two."""
        funcs = [self._fm("a", 1), self._fm("b", 2),
                 self._fm("c", 4), self._fm("d", 8)]
        max_cc, median_cc = aggregate_cc(funcs)
        assert max_cc == 8
        assert median_cc == 3.0  # (2 + 4) / 2

    def test_two_functions(self) -> None:
        funcs = [self._fm("a", 3), self._fm("b", 1)]
        max_cc, median_cc = aggregate_cc(funcs)
        assert max_cc == 3
        assert median_cc == 2.0  # (1 + 3) / 2

    def test_all_same_cc(self) -> None:
        funcs = [self._fm("a", 4), self._fm("b", 4), self._fm("c", 4)]
        assert aggregate_cc(funcs) == (4, 4.0)

    def test_median_rounded_to_one_decimal(self) -> None:
        """Median of [1, 2, 3, 5, 8, 13] = (3+5)/2 = 4.0."""
        funcs = [self._fm(f"f{i}", cc) for i, cc in enumerate([1, 2, 3, 5, 8, 13])]
        max_cc, median_cc = aggregate_cc(funcs)
        assert max_cc == 13
        assert median_cc == 4.0


class TestAggregateCCBaseline:
    def test_empty_function_list_returns_baseline(self) -> None:
        """Files with no functions get baseline CC values, not None.

        This is intentional: any executable code path has minimum CC=1.
        The asymmetry with MI (which is None for empty files) is by design.
        """
        max_cc, median_cc = aggregate_cc([])
        assert max_cc == 1
        assert median_cc == 1.0


# ===========================================================================
# Aggregate MI Tests
# ===========================================================================


class TestAggregateMI:
    @staticmethod
    def _fm(name: str, mi: float | None) -> FunctionMetrics:
        """Helper to create a FunctionMetrics with just name and mi filled."""
        return FunctionMetrics(name=name, line=1, cc=1, loc=1, mi=mi)

    def test_single_function(self) -> None:
        mi_min, mi_median = aggregate_mi([self._fm("f", 100.0)])
        assert mi_min == 100.0
        assert mi_median == 100.0

    def test_multiple_functions(self) -> None:
        funcs = [self._fm("a", 80.0), self._fm("b", 120.0), self._fm("c", 100.0)]
        mi_min, mi_median = aggregate_mi(funcs)
        assert mi_min == 80.0
        assert mi_median == 100.0

    def test_empty_list_returns_none(self) -> None:
        assert aggregate_mi([]) == (None, None)

    def test_all_none_mi_returns_none(self) -> None:
        funcs = [self._fm("a", None), self._fm("b", None)]
        assert aggregate_mi(funcs) == (None, None)

    def test_some_none_mi_excluded(self) -> None:
        """Functions with None MI are excluded from aggregation."""
        funcs = [self._fm("a", 80.0), self._fm("b", None), self._fm("c", 120.0)]
        mi_min, mi_median = aggregate_mi(funcs)
        assert mi_min == 80.0
        assert mi_median == 100.0  # median of [80, 120]

    def test_even_count_median(self) -> None:
        funcs = [self._fm("a", 70.0), self._fm("b", 90.0),
                 self._fm("c", 100.0), self._fm("d", 130.0)]
        mi_min, mi_median = aggregate_mi(funcs)
        assert mi_min == 70.0
        assert mi_median == 95.0  # (90 + 100) / 2

    def test_mi_median_rounded_to_two_decimals(self) -> None:
        funcs = [self._fm("a", 70.33), self._fm("b", 90.67)]
        mi_min, mi_median = aggregate_mi(funcs)
        assert mi_min == 70.33
        assert mi_median == 80.5  # (70.33 + 90.67) / 2 = 80.5


# ===========================================================================
# Halstead Volume Tests
# ===========================================================================


class TestComputeHalsteadVolume:
    def test_empty_file_volume_is_zero(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "empty_file.gd")
        result = compute_halstead_volume(tree)
        assert result.volume == 0.0
        assert result.vocabulary == 0
        assert result.length == 0

    def test_minimal_function(self) -> None:
        """func f(): pass has a small but positive volume."""
        source = "func f():\n\tpass\n"
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_halstead_volume(tree)
        assert result.volume > 0
        assert result.length > 0
        assert result.vocabulary > 0

    def test_helpers_gd_volume(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "utils/helpers.gd")
        result = compute_halstead_volume(tree)
        assert result.length == 19
        assert result.vocabulary == 17
        assert result.volume == pytest.approx(77.66, abs=0.01)

    def test_bullet_gd_volume(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        result = compute_halstead_volume(tree)
        assert result.length == 22
        assert result.vocabulary == 18
        assert result.volume == pytest.approx(91.74, abs=0.01)

    def test_character_gd_volume(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        result = compute_halstead_volume(tree)
        assert result.length == 25
        assert result.vocabulary == 20
        assert result.volume == pytest.approx(108.05, abs=0.01)

    def test_enemy_gd_volume(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "actors/enemy.gd")
        result = compute_halstead_volume(tree)
        assert result.length == 21
        assert result.vocabulary == 19
        assert result.volume == pytest.approx(89.21, abs=0.01)

    def test_player_gd_volume(self, fixtures_dir: Path) -> None:
        _, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_halstead_volume(tree)
        assert result.length == 63
        assert result.vocabulary == 38
        assert result.volume == pytest.approx(330.62, abs=0.01)

    def test_anon_tokens_classified_as_operators(self) -> None:
        """Compound operators like +=, -=, !=, == use __ANON_* token types."""
        source = "var x: int = 0\nfunc f():\n\tx += 1\n\tx -= 2\n"
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_halstead_volume(tree)
        # += and -= should appear as operators, not be dropped
        assert result.length > 0
        assert result.vocabulary > 0

    def test_keyword_recovery_from_subtrees(self) -> None:
        """Keywords like if, for, while, return are recovered from subtree types."""
        source = (
            "func f():\n"
            "\tif true:\n"
            "\t\treturn 1\n"
            "\tfor i in range(5):\n"
            "\t\tpass\n"
            "\twhile false:\n"
            "\t\tpass\n"
        )
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_halstead_volume(tree)
        # Should have: func, if, return, for, pass (x2), while = 7 keyword operators
        # Plus token operators and operands
        assert result.length > 7
        assert result.vocabulary > 0

    def test_no_double_counting_var(self) -> None:
        """class_var_stmt wraps class_var_typed -- 'var' counted once not twice.

        If 'var' were double-counted, length would be 5 instead of 4.
        """
        source = "var x: int = 0\n"
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_halstead_volume(tree)
        assert result.length == 4
        assert result.vocabulary == 4
        assert result.volume == pytest.approx(8.00, abs=0.01)

    def test_no_double_counting_const(self) -> None:
        """const_stmt wraps const_assigned -- 'const' counted once not twice.

        If 'const' were double-counted, length would be 4 instead of 3.
        """
        source = "const X = 5\n"
        tree = gdparser.parse(source, gather_metadata=True)
        result = compute_halstead_volume(tree)
        assert result.length == 3
        assert result.vocabulary == 3
        assert result.volume == pytest.approx(4.75, abs=0.01)


# ===========================================================================
# Maintainability Index Tests
# ===========================================================================


class TestComputeMaintainabilityIndex:
    def test_known_values(self) -> None:
        """Verify MI for helpers.gd: LOC=3, CC=2, V=77.66."""
        mi = compute_maintainability_index(loc=3, cc=2, halstead_volume=77.66)
        assert mi == pytest.approx(130.11, abs=0.1)

    def test_clamped_at_zero(self) -> None:
        """Extremely high V, CC, LOC should produce MI=0 (not negative)."""
        mi = compute_maintainability_index(
            loc=100_000, cc=500, halstead_volume=1_000_000
        )
        assert mi == 0.0

    def test_simple_low_complexity(self) -> None:
        """Small file with low complexity should have high MI."""
        mi = compute_maintainability_index(loc=2, cc=1, halstead_volume=20.0)
        assert mi > 100
        assert mi <= 171

    def test_raises_on_zero_loc(self) -> None:
        """loc=0 must raise ValueError (math.log(0) is undefined)."""
        with pytest.raises(ValueError, match="loc must be > 0"):
            compute_maintainability_index(loc=0, cc=1, halstead_volume=10.0)

    def test_raises_on_negative_loc(self) -> None:
        """Negative loc must also raise ValueError."""
        with pytest.raises(ValueError, match="loc must be > 0"):
            compute_maintainability_index(loc=-1, cc=1, halstead_volume=10.0)

    def test_raises_on_zero_volume(self) -> None:
        """halstead_volume=0 must raise ValueError (math.log(0) is undefined)."""
        with pytest.raises(ValueError, match="halstead_volume must be > 0"):
            compute_maintainability_index(loc=5, cc=1, halstead_volume=0.0)

    def test_raises_on_negative_volume(self) -> None:
        """Negative halstead_volume must also raise ValueError."""
        with pytest.raises(ValueError, match="halstead_volume must be > 0"):
            compute_maintainability_index(loc=5, cc=1, halstead_volume=-1.0)


# ===========================================================================
# compute_metrics Tests
# ===========================================================================


class TestComputeMetrics:
    def test_with_valid_tree(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        result = compute_metrics(source, tree)

        assert isinstance(result, FileMetrics)
        assert result.loc == 9
        assert result.max_cc == 2       # max of take_damage(2), get_bullet(1)
        assert result.median_cc == 1.5  # median of [2, 1]
        assert result.mi is not None
        assert isinstance(result.mi, float)
        assert 0 <= result.mi <= 171

    def test_with_none_tree(self) -> None:
        source = "this is not valid gdscript @@@\n"
        result = compute_metrics(source, None)

        assert isinstance(result, FileMetrics)
        assert result.loc == 1
        assert result.max_cc is None
        assert result.median_cc is None
        assert result.mi is None
        assert result.mi_min is None
        assert result.mi_median is None
        assert result.functions == []

    def test_empty_source_with_none_tree(self) -> None:
        result = compute_metrics("", None)

        assert result.loc == 0
        assert result.max_cc is None
        assert result.median_cc is None
        assert result.mi is None
        assert result.mi_min is None
        assert result.mi_median is None
        assert result.functions == []

    def test_empty_file_with_valid_tree(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "empty_file.gd")
        result = compute_metrics(source, tree)

        assert result.loc == 0
        assert result.max_cc == 1     # baseline (no functions)
        assert result.median_cc == 1.0
        assert result.mi is None  # LOC=0 makes MI undefined
        assert result.mi_min is None  # no functions
        assert result.mi_median is None
        assert result.functions == []

    def test_returns_filemetrics_dataclass(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        result = compute_metrics(source, tree)

        assert isinstance(result, FileMetrics)
        assert result.loc == 5
        assert result.max_cc == 1
        assert result.median_cc == 1.0
        assert result.mi is not None

    def test_mi_value_for_helpers(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "utils/helpers.gd")
        result = compute_metrics(source, tree)
        assert result.mi == pytest.approx(130.11, abs=0.1)

    def test_mi_value_for_bullet(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "weapons/bullet.gd")
        result = compute_metrics(source, tree)
        assert result.mi == pytest.approx(121.20, abs=0.1)

    def test_mi_value_for_character(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        result = compute_metrics(source, tree)
        assert result.mi == pytest.approx(110.60, abs=0.1)

    def test_mi_value_for_enemy(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "actors/enemy.gd")
        result = compute_metrics(source, tree)
        assert result.mi == pytest.approx(117.93, abs=0.1)

    def test_mi_value_for_player(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_metrics(source, tree)
        assert result.mi == pytest.approx(94.25, abs=0.1)

    def test_functions_list_for_character(self, fixtures_dir: Path) -> None:
        """compute_metrics includes full per-function detail."""
        source, tree = _parse_fixture(fixtures_dir, "actors/character.gd")
        result = compute_metrics(source, tree)
        names = {f.name for f in result.functions}
        assert names == {"take_damage", "get_bullet"}
        assert len(result.functions) == 2

    def test_functions_list_for_player(self, fixtures_dir: Path) -> None:
        source, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_metrics(source, tree)
        names = {f.name for f in result.functions}
        assert names == {"_process", "shoot"}

    def test_mi_min_and_mi_median_for_player(self, fixtures_dir: Path) -> None:
        """player.gd: _process has lower MI than shoot (more complex)."""
        source, tree = _parse_fixture(fixtures_dir, "actors/player.gd")
        result = compute_metrics(source, tree)
        assert result.mi_min is not None
        assert result.mi_median is not None

        by_name = {f.name: f for f in result.functions}
        # mi_min should be the worst (lowest) function MI
        assert result.mi_min == min(f.mi for f in result.functions if f.mi is not None)
        # _process is more complex, should have lower MI
        assert by_name["_process"].mi < by_name["shoot"].mi

    def test_mi_min_equals_mi_for_single_function(self, fixtures_dir: Path) -> None:
        """For a file with one function, mi_min == mi_median == that function's MI."""
        source, tree = _parse_fixture(fixtures_dir, "actors/enemy.gd")
        result = compute_metrics(source, tree)
        assert result.mi_min is not None
        assert result.mi_median is not None
        assert result.mi_min == result.mi_median
        assert result.mi_min == result.functions[0].mi
