"""DAG 规划器 - 构建依赖图并检测循环"""

from loguru import logger

from nextgen.core.model import TestCase


def build_graph(testcase: TestCase) -> dict[str, list[str]]:
    """构建依赖图

    返回: {step_name: [dep1, dep2, ...]}
    """
    graph = {
        name: step.depends_on
        for name, step in testcase.steps.items()
    }
    logger.debug(f"构建依赖图: {graph}")
    return graph


def detect_cycle(graph: dict[str, list[str]]) -> None:
    """检测依赖图中的循环

    使用 DFS 检测，发现循环时抛出异常
    """
    visited: set[str] = set()
    stack: set[str] = set()

    def visit(node: str) -> None:
        if node in stack:
            raise ValueError(f"检测到循环依赖，涉及节点: {node}")
        if node in visited:
            return

        stack.add(node)

        for dep in graph.get(node, []):
            if dep not in graph:
                raise ValueError(f"依赖的步骤不存在: {node} -> {dep}")
            visit(dep)

        stack.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

    logger.debug("依赖图无循环")


def get_execution_order(graph: dict[str, list[str]]) -> list[list[str]]:
    """获取执行顺序（拓扑排序）

    返回分层列表，同一层的步骤可并行执行
    """
    # 计算入度
    in_degree = {node: 0 for node in graph}
    for node in graph:
        for dep in graph[node]:
            in_degree[node] += 1

    # 分层拓扑排序
    layers: list[list[str]] = []
    remaining = set(graph.keys())

    while remaining:
        # 找出入度为 0 的节点
        layer = [n for n in remaining if in_degree[n] == 0]
        if not layer:
            raise ValueError("无法确定执行顺序，可能存在循环")

        layers.append(layer)

        # 更新入度
        for node in layer:
            remaining.remove(node)
            for other in remaining:
                if node in graph[other]:
                    in_degree[other] -= 1

    logger.debug(f"执行顺序: {layers}")
    return layers


def validate_testcase(testcase: TestCase) -> None:
    """验证测试用例"""
    graph = build_graph(testcase)
    detect_cycle(graph)
    logger.info(f"测试用例验证通过，共 {len(testcase.steps)} 个步骤")
