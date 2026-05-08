"""planner.py 单元测试"""

import pytest

from nextgen.core.model import ActionNode, StepNode, TestCase as CaseModel
from nextgen.core.planner import build_graph, detect_cycle, get_execution_order


def make_step(name: str, depends_on: list[str] | None = None) -> StepNode:
    """创建测试用 StepNode"""
    return StepNode(
        name=name,
        action=ActionNode(
            type="request",
            config={"method": "GET", "url": "http://test.com"},
        ),
        depends_on=depends_on or [],
    )


class TestBuildGraph:
    """测试 build_graph"""

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

    def test_sequential_mode_auto_dependencies(self):
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
        assert graph == {"a": [], "b": ["a"], "c": ["b"]}

    def test_sequential_mode_with_explicit_dependencies(self):
        testcase = CaseModel(
            version=1,
            steps={
                "a": make_step("a"),
                "b": make_step("b"),
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
    """测试 detect_cycle"""

    def test_no_cycle(self):
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        detect_cycle(graph)  # 不应抛出异常

    def test_simple_cycle(self):
        graph = {"a": ["b"], "b": ["a"]}
        with pytest.raises(ValueError, match="循环依赖"):
            detect_cycle(graph)

    def test_self_cycle(self):
        graph = {"a": ["a"]}
        with pytest.raises(ValueError, match="循环依赖"):
            detect_cycle(graph)

    def test_indirect_cycle(self):
        graph = {"a": ["c"], "b": ["a"], "c": ["b"]}
        with pytest.raises(ValueError, match="循环依赖"):
            detect_cycle(graph)

    def test_missing_dependency(self):
        graph = {"a": ["b"]}
        with pytest.raises(ValueError, match="不存在"):
            detect_cycle(graph)


class TestGetExecutionOrder:
    """测试 get_execution_order"""

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
        # 第一层：a, b（可并行）
        assert set(order[0]) == {"a", "b"}
        # 第二层：c, d（可并行）
        assert set(order[1]) == {"c", "d"}
