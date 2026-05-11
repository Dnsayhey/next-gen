"""Step tag filtering for testcases."""

from dataclasses import replace

from nextgen.core.errors import ParseError
from nextgen.core.model import TestCase
from nextgen.core.planner import build_graph, validate_testcase


def filter_testcase_by_tags(
    testcase: TestCase,
    include_tags: set[str] | None = None,
    skip_tags: set[str] | None = None,
) -> TestCase:
    """Filter testcase steps by tags while preserving dependency validity."""
    include_tags = include_tags or set()
    skip_tags = skip_tags or set()
    if not include_tags and not skip_tags:
        return testcase

    graph = build_graph(testcase)
    skipped = {
        name
        for name, step in testcase.steps.items()
        if set(step.tags) & skip_tags
    }

    if include_tags:
        targets = {
            name
            for name, step in testcase.steps.items()
            if set(step.tags) & include_tags
        }
    else:
        targets = set(testcase.steps)

    selected: set[str] = set()
    for target in targets:
        if target in skipped:
            continue
        selected.add(target)
        for dep in dependency_closure(target, graph):
            if dep in skipped:
                raise ParseError(
                    f"tag filter conflict: step '{target}' requires skipped dependency '{dep}'"
                )
            selected.add(dep)

    selected -= skipped
    if not selected:
        raise ParseError("tag filter selected no steps")

    filtered = replace(
        testcase,
        steps={
            name: step
            for name, step in testcase.steps.items()
            if name in selected
        },
    )
    validate_testcase(filtered)
    return filtered


def dependency_closure(step_name: str, graph: dict[str, list[str]]) -> set[str]:
    """Return all transitive dependencies for one step."""
    deps: set[str] = set()

    def visit(name: str) -> None:
        for dep in graph[name]:
            if dep in deps:
                continue
            deps.add(dep)
            visit(dep)

    visit(step_name)
    return deps
