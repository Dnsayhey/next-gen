"""DSL parser for YAML and JSON formats."""

from copy import deepcopy
from enum import Enum
from itertools import product
import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from nextgen.core.actions import list_actions, get_action
from nextgen.core.errors import ParseError
from nextgen.core.model import (
    ActionNode,
    AndCondition,
    AssertionNode,
    ConditionNode,
    ExprCondition,
    HookAction,
    OrCondition,
    StepNode,
    StepHooks,
    Suite,
    TestCase,
    TestCaseHooks,
)

SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}


class FileKind(str, Enum):
    """Supported runnable file kinds."""

    TESTCASE = "testcase"
    SUITE = "suite"


def load_file(path: str | Path) -> dict[str, Any]:
    """Load a testcase file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"testcase file does not exist: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ParseError(f"unsupported file format: {ext}; supported: {SUPPORTED_EXTENSIONS}")

    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ParseError(f"invalid file format: expected dict, got {type(data).__name__}")

    logger.debug(f"Loaded file: {path}")
    return data


def classify_loaded_file(data: dict[str, Any]) -> FileKind:
    """Classify a loaded YAML/JSON file as testcase or suite."""
    has_steps = "steps" in data
    has_tests = "tests" in data

    if has_steps and has_tests:
        raise ParseError("ambiguous file format: contains both 'steps' and 'tests'")
    if has_steps:
        return FileKind.TESTCASE
    if has_tests:
        return FileKind.SUITE
    raise ParseError("unrecognized file format: expected 'steps' or 'tests'")


def classify_file(path: str | Path) -> FileKind:
    """Load and classify a YAML/JSON file."""
    return classify_loaded_file(load_file(path))


def normalize_path_list(data: Any, field: str) -> list[str]:
    """Parse a suite path list field."""
    if data is None:
        return []
    if not isinstance(data, list):
        raise ParseError(f"invalid suite {field} format: expected list")

    paths: list[str] = []
    for item in data:
        if not isinstance(item, str):
            raise ParseError(f"invalid suite {field} path: expected str, got {type(item).__name__}")
        if not item:
            raise ParseError(f"invalid suite {field} path: expected non-empty str")
        paths.append(item)
    return paths


def parse_suite(data: dict[str, Any]) -> Suite:
    """Parse a suite file."""
    if "tests" not in data:
        raise ParseError("missing tests field")

    tests = normalize_path_list(data["tests"], "tests")
    if not tests:
        raise ParseError("missing tests field or tests is empty")

    name = data.get("name", "suite")
    if not isinstance(name, str) or not name:
        raise ParseError("invalid suite name: expected non-empty str")

    return Suite(
        name=name,
        env=normalize_path_list(data.get("env"), "env"),
        setup=normalize_path_list(data.get("setup"), "setup"),
        tests=tests,
    )


def load_suite(path: str | Path) -> Suite:
    """Load a suite from a YAML/JSON file."""
    path = Path(path).resolve()
    data = load_file(path)
    kind = classify_loaded_file(data)
    if kind != FileKind.SUITE:
        raise ParseError(f"not a suite file: {path}")

    suite = parse_suite(data)
    suite.source_path = str(path)
    suite.base_dir = str(path.parent)
    suite.env = [str((path.parent / env_path).resolve()) for env_path in suite.env]
    suite.setup = [str((path.parent / setup_path).resolve()) for setup_path in suite.setup]
    suite.tests = [str((path.parent / test_path).resolve()) for test_path in suite.tests]
    logger.info(f"Parsed suite: {path}, tests={len(suite.tests)}, setup={len(suite.setup)}")
    return suite


def find_action_type(data: dict[str, Any]) -> str | None:
    """Find the action type in step data."""
    for action_type in list_actions():
        if action_type in data:
            return action_type
    return None


def parse_assertions(data: list[dict[str, Any]]) -> list[AssertionNode]:
    """Parse validate assertions.

    Format: [{eq: [$.code, 0]}, {contains: [$.data.name, "test"]}]
    """
    assertions = []

    for item in data:
        if not isinstance(item, dict) or len(item) != 1:
            raise ParseError(f"invalid assertion format: {item}")

        op = list(item.keys())[0]
        args = item[op]

        if not isinstance(args, list) or len(args) != 2:
            raise ParseError(f"invalid assertion args: {op} requires two args [left, right]")

        assertions.append(AssertionNode(op=op, left=args[0], right=args[1]))

    return assertions


def parse_when(data: list | dict | None) -> ConditionNode | None:
    """Parse a when condition.

    Format:
    - list: [{eq: [$.code, 0]}, ...] -> implicit AND
    - dict: {and: [...]} or {or: [...]} -> explicit logic
    """
    if data is None:
        return None

    if isinstance(data, list):
        return AndCondition([parse_when_item(item) for item in data])

    if isinstance(data, dict):
        if "and" in data:
            return AndCondition([parse_when_item(item) for item in data["and"]])
        if "or" in data:
            return OrCondition([parse_when_item(item) for item in data["or"]])
        raise ParseError(f"invalid when format: dict must include 'and' or 'or', got {list(data.keys())}")

    raise ParseError(f"invalid when format: expected list or dict, got {type(data).__name__}")


def parse_when_item(item: dict[str, Any]) -> ConditionNode:
    """Parse one when condition item."""
    if not isinstance(item, dict):
        raise ParseError(f"invalid condition item format: {item}")

    if "and" in item:
        return AndCondition([parse_when_item(child) for child in item["and"]])
    if "or" in item:
        return OrCondition([parse_when_item(child) for child in item["or"]])

    if len(item) != 1:
        raise ParseError(f"invalid expression format: {item}")

    op = list(item.keys())[0]
    args = item[op]
    if not isinstance(args, list) or len(args) != 2:
        raise ParseError(f"invalid expression args: {op} requires two args [left, right]")

    return ExprCondition(op=op, left=args[0], right=args[1])


def parse_hook_action(data: dict[str, Any]) -> HookAction:
    """Parse one hook action."""
    if not isinstance(data, dict) or len(data) != 1:
        raise ParseError(f"invalid hook format: {data}")

    hook_type = list(data.keys())[0]
    raw_params = data[hook_type]

    return HookAction(type=hook_type, params=raw_params if raw_params is not None else {})


def expand_step_matrix(name: str, data: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Expand a step matrix template."""
    matrix = data.get("matrix")
    if matrix is None:
        return [(name, deepcopy(data), {})]

    if not isinstance(matrix, dict) or not matrix:
        raise ParseError(f"step '{name}' has invalid matrix format: expected a non-empty dict")

    keys = list(matrix.keys())
    value_lists: list[list[Any]] = []
    for key in keys:
        values = matrix[key]
        if not isinstance(values, list) or not values:
            raise ParseError(f"step '{name}' matrix variable '{key}' must be a non-empty list")
        value_lists.append(values)

    base_data = deepcopy(data)
    base_data.pop("matrix", None)

    variants: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for values in product(*value_lists):
        matrix_vars = dict(zip(keys, values))
        suffix = ",".join(f"{key}={value}" for key, value in matrix_vars.items())
        instance_name = f"{name}[{suffix}]"
        variants.append((instance_name, deepcopy(base_data), matrix_vars))

    return variants


def parse_step_hooks(data: dict[str, Any] | None) -> StepHooks:
    """Parse step-level hooks."""
    if data is None:
        return StepHooks()
    if not isinstance(data, dict):
        raise ParseError(f"invalid step hooks format: expected dict, got {type(data).__name__}")

    return StepHooks(
        before=[parse_hook_action(item) for item in data.get("before", [])],
        after=[parse_hook_action(item) for item in data.get("after", [])],
    )


def parse_testcase_hooks(data: dict[str, Any] | None) -> TestCaseHooks:
    """Parse testcase-level hooks."""
    if data is None:
        return TestCaseHooks()
    if not isinstance(data, dict):
        raise ParseError(f"invalid testcase hooks format: expected dict, got {type(data).__name__}")

    return TestCaseHooks(
        before_all=[parse_hook_action(item) for item in data.get("before_all", [])],
        after_all=[parse_hook_action(item) for item in data.get("after_all", [])],
        before_each=[parse_hook_action(item) for item in data.get("before_each", [])],
        after_each=[parse_hook_action(item) for item in data.get("after_each", [])],
    )


def resolve_depends_on(depends_on: list[str], matrix_map: dict[str, list[str]]) -> list[str]:
    """Resolve template dependencies into concrete step dependencies."""
    resolved: list[str] = []
    for dep in depends_on:
        if dep not in matrix_map:
            raise ParseError(f"dependency step does not exist: {dep}")
        resolved.extend(matrix_map[dep])
    return resolved


def parse_step(name: str, data: dict[str, Any]) -> StepNode:
    """Parse one step."""
    # Find action type.
    action_type = find_action_type(data)

    if not action_type:
        raise ParseError(
            f"step '{name}' is missing an action field; "
            f"supported action types: {list_actions()}"
        )

    # Check whether multiple actions are present.
    found_actions = [a for a in list_actions() if a in data]
    if len(found_actions) > 1:
        raise ParseError(
            f"step '{name}' contains multiple actions: {found_actions}; only one is allowed"
        )

    action = get_action(action_type)
    if action is None:
        raise ParseError(f"unregistered action type: {action_type}")

    parsed_config = action.parse_config(data[action_type])

    return StepNode(
        name=name,
        action=ActionNode(type=action_type, config=parsed_config),
        depends_on=data.get("depends_on", []),
        extract=data.get("extract", {}),
        export=data.get("export", {}),
        validate=parse_assertions(data.get("validate", [])),
        when=parse_when(data.get("when")),
        set_vars=data.get("set_vars", {}),
        config=data.get("config", {}),
        hooks=parse_step_hooks(data.get("hooks")),
    )


def parse_testcase(data: dict[str, Any]) -> TestCase:
    """Parse an entire testcase."""
    if "version" not in data:
        raise ParseError("missing version field")

    if "steps" not in data or not data["steps"]:
        raise ParseError("missing steps field or steps is empty")

    mode = data.get("mode", "sequential")
    if mode not in ("sequential", "parallel"):
        raise ParseError(f"unsupported execution mode: {mode}; supported: sequential, parallel")

    fail_fast = data.get("fail_fast", True)
    if not isinstance(fail_fast, bool):
        raise ParseError(f"invalid fail_fast format: expected bool, got {type(fail_fast).__name__}")

    steps: dict[str, StepNode] = {}
    matrix_map: dict[str, list[str]] = {}

    for name, raw in data["steps"].items():
        variants = expand_step_matrix(name, raw)
        matrix_map[name] = [variant_name for variant_name, _, _ in variants]

        for variant_name, variant_data, matrix_vars in variants:
            step = parse_step(variant_name, variant_data)

            if matrix_vars:
                conflict = set(matrix_vars) & set(step.set_vars)
                if conflict:
                    raise ParseError(
                        f"step '{name}' matrix variables conflict with set_vars: {sorted(conflict)}"
                    )
                step.set_vars = {**matrix_vars, **step.set_vars}

            if step.name in steps:
                raise ParseError(f"duplicate step name: {step.name}")

            steps[step.name] = step

    for step in steps.values():
        step.depends_on = resolve_depends_on(step.depends_on, matrix_map)

    return TestCase(
        version=data["version"],
        vars=data.get("vars", {}),
        steps=steps,
        mode=mode,
        fail_fast=fail_fast,
        hooks=parse_testcase_hooks(data.get("hooks")),
    )


def load_testcase(path: str | Path) -> TestCase:
    """Load a testcase from a YAML/JSON file."""
    path = Path(path).resolve()
    data = load_file(path)
    testcase = parse_testcase(data)
    testcase.source_path = str(path)
    testcase.base_dir = str(path.parent)
    logger.info(f"Parsed testcase: {path}, steps={len(testcase.steps)}")
    return testcase
