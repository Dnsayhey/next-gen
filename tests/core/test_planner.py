"""planner.py unit tests"""

import pytest

from nextgen.core.errors import ParseError
from nextgen.core.model import ActionNode, StepNode, TestCase as CaseModel
from nextgen.core.planner import build_graph, detect_cycle, get_execution_order


def make_step(name: str, depends_on: list[str] | None = None) -> StepNode:
    """Create a test StepNode"""
    return StepNode(
        name=name,
        action=ActionNode(
            type="request",
            config={"method": "GET", "url": "http://test.com"},
        ),
        depends_on=depends_on or [],
    )


class TestBuildGraph:
    """Test build_graph"""

    def test_parallel_mode_no_dependencies(self):
        testcase = CaseModel(
            version=1,
            steps={
                "a": make_step("a"),
                "b": make_step("b"),
            },
            mode="parallel",
        )
        graph = build_graph(testcase)
        assert graph == {"a": [], "b": []}

    def test_sequential_mode_has_no_implicit_dependencies(self):
        testcase = CaseModel(
            version=1,
            steps={
                "a": make_step("a"),
                "b": make_step("b"),
                "c": make_step("c"),
            },
            mode="sequential",
        )
        graph = build_graph(testcase)
        assert graph == {"a": [], "b": [], "c": []}

    def test_sequential_mode_with_explicit_dependencies(self):
        testcase = CaseModel(
            version=1,
            steps={
                "a": make_step("a"),
                "b": make_step("b", ["a"]),
                "c": make_step("c", ["a"]),
            },
            mode="sequential",
        )
        graph = build_graph(testcase)
        assert graph == {"a": [], "b": ["a"], "c": ["a"]}

    def test_with_dependencies(self):
        testcase = CaseModel(
            version=1,
            steps={
                "a": make_step("a"),
                "b": make_step("b", ["a"]),
            },
        )
        graph = build_graph(testcase)
        assert graph == {"a": [], "b": ["a"]}


class TestDetectCycle:
    """Test detect_cycle"""

    def test_no_cycle(self):
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        detect_cycle(graph)  # Should not raise.

    def test_simple_cycle(self):
        graph = {"a": ["b"], "b": ["a"]}
        with pytest.raises(ParseError, match="cycle"):
            detect_cycle(graph)

    def test_self_cycle(self):
        graph = {"a": ["a"]}
        with pytest.raises(ValueError, match="cycle"):
            detect_cycle(graph)

    def test_indirect_cycle(self):
        graph = {"a": ["c"], "b": ["a"], "c": ["b"]}
        with pytest.raises(ValueError, match="cycle"):
            detect_cycle(graph)

    def test_missing_dependency(self):
        graph = {"a": ["b"]}
        with pytest.raises(ValueError, match="does not exist"):
            detect_cycle(graph)


class TestGetExecutionOrder:
    """Test get_execution_order"""

    def test_single_step(self):
        graph = {"a": []}
        order = get_execution_order(graph)
        assert order == [["a"]]

    def test_sequential(self):
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        order = get_execution_order(graph)
        assert order == [["a"], ["b"], ["c"]]

    def test_parallel(self):
        graph = {"a": [], "b": [], "c": ["a", "b"]}
        order = get_execution_order(graph)
        assert order[0] == ["a", "b"] or order[0] == ["b", "a"]
        assert order[1] == ["c"]

    def test_mixed(self):
        graph = {"a": [], "b": [], "c": ["a"], "d": ["a", "b"]}
        order = get_execution_order(graph)
        # First layer: a, b (parallelizable)
        assert set(order[0]) == {"a", "b"}
        # Second layer: c, d (parallelizable)
        assert set(order[1]) == {"c", "d"}
