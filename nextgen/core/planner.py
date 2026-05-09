"""DAG planner for dependency graphs and cycle detection."""

from loguru import logger

from nextgen.core.errors import ParseError
from nextgen.core.model import TestCase


def build_graph(testcase: TestCase) -> dict[str, list[str]]:
    """Build a dependency graph.

    Returns: {step_name: [dep1, dep2, ...]}
    """
    graph = {}
    for name, step in testcase.steps.items():
        graph[name] = step.depends_on or []

    logger.debug(f"Built dependency graph: {graph}")
    return graph


def detect_cycle(graph: dict[str, list[str]]) -> None:
    """Detect cycles in a dependency graph.

    Uses DFS and raises when a cycle is found.
    """
    visited: set[str] = set()
    stack: set[str] = set()

    def visit(node: str) -> None:
        if node in stack:
            raise ParseError(f"cycle detected involving node: {node}")
        if node in visited:
            return

        stack.add(node)

        for dep in graph.get(node, []):
            if dep not in graph:
                raise ParseError(f"dependency step does not exist: {node} -> {dep}")
            visit(dep)

        stack.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)

    logger.debug("Dependency graph has no cycles")


def get_execution_order(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return execution order via topological sorting.

    Returns layered lists. Steps in the same layer can run in parallel.
    This is a planner helper for dry-run, visualization, and debugging;
    the current scheduler uses runtime dynamic scheduling instead.
    """
    # Compute indegrees.
    in_degree = {node: 0 for node in graph}
    for node in graph:
        for dep in graph[node]:
            in_degree[node] += 1

    # Layered topological sort.
    layers: list[list[str]] = []
    remaining = set(graph.keys())

    while remaining:
        # Find nodes with zero indegree.
        layer = [n for n in remaining if in_degree[n] == 0]
        if not layer:
            raise ParseError("unable to determine execution order; a cycle may exist")

        layers.append(layer)

        # Update indegrees.
        for node in layer:
            remaining.remove(node)
            for other in remaining:
                if node in graph[other]:
                    in_degree[other] -= 1

    logger.debug(f"Execution order: {layers}")
    return layers


def validate_testcase(testcase: TestCase) -> None:
    """Validate a testcase."""
    graph = build_graph(testcase)
    detect_cycle(graph)
    logger.info(f"Testcase validation passed with {len(testcase.steps)} steps")
