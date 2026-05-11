"""Dry-run execution plan serialization."""

from pathlib import Path
from typing import Any

from nextgen.core.actions import get_action
from nextgen.core.files import dedupe_paths
from nextgen.core.filtering import filter_testcase_by_tags
from nextgen.core.hooks import discover_hooks
from nextgen.core.model import StepNode, Suite, TestCase
from nextgen.core.planner import build_graph, get_execution_order, validate_testcase
from nextgen.parser.env_loader import load_env_files
from nextgen.parser.loader import FileKind, classify_file, load_suite, load_testcase


def dry_run_inputs(
    files: list[Path],
    env_files: list[Path],
    include_tags: set[str] | None = None,
    skip_tags: set[str] | None = None,
) -> dict[str, Any]:
    """Build a dry-run plan for CLI inputs."""
    # Keep these input classification rules aligned with cli.run_inputs.
    if not files:
        raise ValueError("at least one file is required")

    if len(files) == 1:
        kind = classify_file(files[0])
        if kind == FileKind.SUITE:
            return dry_run_suite(load_suite(files[0]), env_files, include_tags, skip_tags)
        return dry_run_testcase(files[0], env_files, include_tags=include_tags, skip_tags=skip_tags)

    kinds = [classify_file(file) for file in files]
    if any(kind == FileKind.SUITE for kind in kinds):
        raise ValueError("suite files cannot be mixed with other CLI inputs")

    suite = Suite(
        name="cli",
        tests=[str(path) for path in dedupe_paths(files)],
    )
    return dry_run_suite(suite, env_files, include_tags, skip_tags)


def dry_run_suite(
    suite: Suite,
    cli_env_files: list[Path],
    include_tags: set[str] | None = None,
    skip_tags: set[str] | None = None,
) -> dict[str, Any]:
    """Build a dry-run plan for a suite."""
    suite_env = load_env_files(suite.env)
    cli_env = load_env_files(cli_env_files)
    env = {**suite_env, **cli_env}

    setup = [
        dry_run_testcase(path, [], env, include_tags, skip_tags)
        for path in suite.setup
    ]
    tests = [
        dry_run_testcase(path, [], env, include_tags, skip_tags)
        for path in suite.tests
    ]

    return {
        "suite": suite.name,
        "env_keys": sorted(env),
        "filters": serialize_filters(include_tags, skip_tags),
        "setup_export_keys": sorted({
            key
            for plan in setup
            for key in plan["declared_export_keys"]
        }),
        "runtime_setup_exports": True,
        "setup": setup,
        "tests": tests,
    }


def dry_run_testcase(
    path: str | Path,
    env_files: list[Path],
    env: dict[str, Any] | None = None,
    include_tags: set[str] | None = None,
    skip_tags: set[str] | None = None,
) -> dict[str, Any]:
    """Build a dry-run plan for one testcase."""
    testcase = load_testcase(path)
    testcase.vars = {
        **testcase.vars,
        **(env or {}),
        **load_env_files(env_files),
    }
    validate_testcase(testcase)
    testcase = filter_testcase_by_tags(testcase, include_tags, skip_tags)

    graph = build_graph(testcase)
    plan = serialize_testcase_plan(
        testcase,
        graph,
        get_execution_order(graph),
    )
    plan["filters"] = serialize_filters(include_tags, skip_tags)
    return plan


def serialize_testcase_plan(
    testcase: TestCase,
    graph: dict[str, list[str]],
    execution_order: list[list[str]],
) -> dict[str, Any]:
    """Serialize an already loaded and validated testcase as a dry-run plan."""
    hook_files = []
    if testcase.source_path:
        hook_files = [
            str(path)
            for path in discover_hooks(
                testcase.source_path,
                testcase.base_dir or ".",
            )
        ]

    return {
        "testcase": testcase.source_path or "",
        "mode": testcase.mode,
        "fail_fast": testcase.fail_fast,
        "env_keys": sorted(testcase.vars),
        "hook_files": hook_files,
        "declared_export_keys": sorted({
            key
            for step in testcase.steps.values()
            for key in step.export
        }),
        "steps": [
            serialize_step(step, graph[step.name])
            for step in testcase.steps.values()
        ],
        "execution_order": execution_order,
    }


def serialize_step(step: StepNode, depends_on: list[str]) -> dict[str, Any]:
    """Serialize one step without rendering runtime variables."""
    action = get_action(step.action.type)
    summary = (
        action.summarize(step.action.config)
        if action is not None
        else step.action.type
    )

    return {
        "name": step.name,
        "action": step.action.type,
        "tags": step.tags,
        "summary": summary,
        "depends_on": depends_on,
        "has_when": step.when is not None,
        "hooks": {
            "before": len(step.hooks.before),
            "after": len(step.hooks.after),
        },
        "timeout": step.config.get("timeout"),
        "retry": step.config.get("retry", 0),
    }


def serialize_filters(
    include_tags: set[str] | None,
    skip_tags: set[str] | None,
) -> dict[str, list[str]]:
    """Serialize active tag filters."""
    return {
        "tags": sorted(include_tags or []),
        "skip_tags": sorted(skip_tags or []),
    }
