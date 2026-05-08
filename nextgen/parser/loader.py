"""DSL 解析器 - 支持 YAML 和 JSON 格式"""

from copy import deepcopy
from itertools import product
import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from nextgen.core.actions import list_actions, get_action
from nextgen.core.model import (
    ActionNode,
    AssertionNode,
    HookAction,
    StepNode,
    StepHooks,
    TestCase,
    TestCaseHooks,
)

SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}


def load_file(path: str | Path) -> dict[str, Any]:
    """加载测试用例文件（支持 YAML / JSON）"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"测试用例文件不存在: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，支持: {SUPPORTED_EXTENSIONS}")

    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"文件格式错误，期望 dict，得到 {type(data).__name__}")

    logger.debug(f"加载文件: {path}")
    return data


def find_action_type(data: dict[str, Any]) -> str | None:
    """从 step 数据中找到 action 类型"""
    for action_type in list_actions():
        if action_type in data:
            return action_type
    return None


def parse_assertions(data: list[dict[str, Any]]) -> list[AssertionNode]:
    """解析 validate 断言列表

    格式: [{eq: [$.code, 0]}, {contains: [$.data.name, "test"]}]
    """
    assertions = []

    for item in data:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError(f"断言格式错误: {item}")

        op = list(item.keys())[0]
        args = item[op]

        if not isinstance(args, list) or len(args) != 2:
            raise ValueError(f"断言参数错误: {op} 需要两个参数 [left, right]")

        assertions.append(AssertionNode(op=op, left=args[0], right=args[1]))

    return assertions


def parse_when(data: list | dict | None) -> list | dict | None:
    """解析 when 条件

    格式:
    - list: [{eq: [$.code, 0]}, ...]  → 默认 AND
    - dict: {and: [...]} 或 {or: [...]}  → 显式逻辑
    """
    if data is None:
        return None

    if isinstance(data, list):
        # 列表格式，默认 AND，直接返回
        return data

    if isinstance(data, dict):
        if "and" in data:
            return {"and": data["and"]}
        if "or" in data:
            return {"or": data["or"]}
        raise ValueError(f"when 格式错误: dict 必须包含 and 或 or 键，得到 {list(data.keys())}")

    raise ValueError(f"when 格式错误: 期望 list 或 dict，得到 {type(data).__name__}")


def parse_hook_action(data: dict[str, Any]) -> HookAction:
    """解析单个 hook 动作"""
    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError(f"hook 格式错误: {data}")

    hook_type = list(data.keys())[0]
    raw_params = data[hook_type]

    if isinstance(raw_params, dict):
        params = raw_params
    elif hook_type == "sleep":
        params = {"seconds": raw_params}
    elif hook_type == "log":
        params = {"message": raw_params}
    elif hook_type in {"getTimestamp", "getTimeStr", "getRandomStr"}:
        params = {"var": raw_params}
    elif raw_params is None:
        params = {}
    else:
        params = {"value": raw_params}

    return HookAction(type=hook_type, params=params)


def expand_step_matrix(name: str, data: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """展开 step matrix 模板"""
    matrix = data.get("matrix")
    if matrix is None:
        return [(name, deepcopy(data), {})]

    if not isinstance(matrix, dict) or not matrix:
        raise ValueError(f"step '{name}' 的 matrix 格式错误: 期望非空 dict")

    keys = list(matrix.keys())
    value_lists: list[list[Any]] = []
    for key in keys:
        values = matrix[key]
        if not isinstance(values, list) or not values:
            raise ValueError(f"step '{name}' 的 matrix 变量 '{key}' 必须是非空 list")
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
    """解析步骤级 hooks"""
    if data is None:
        return StepHooks()
    if not isinstance(data, dict):
        raise ValueError(f"step hooks 格式错误: 期望 dict，得到 {type(data).__name__}")

    return StepHooks(
        before=[parse_hook_action(item) for item in data.get("before", [])],
        after=[parse_hook_action(item) for item in data.get("after", [])],
    )


def parse_testcase_hooks(data: dict[str, Any] | None) -> TestCaseHooks:
    """解析用例级 hooks"""
    if data is None:
        return TestCaseHooks()
    if not isinstance(data, dict):
        raise ValueError(f"testcase hooks 格式错误: 期望 dict，得到 {type(data).__name__}")

    return TestCaseHooks(
        before_all=[parse_hook_action(item) for item in data.get("before_all", [])],
        after_all=[parse_hook_action(item) for item in data.get("after_all", [])],
        before_each=[parse_hook_action(item) for item in data.get("before_each", [])],
        after_each=[parse_hook_action(item) for item in data.get("after_each", [])],
    )


def resolve_depends_on(depends_on: list[str], matrix_map: dict[str, list[str]]) -> list[str]:
    """将模板依赖展开为具体步骤依赖"""
    resolved: list[str] = []
    for dep in depends_on:
        if dep not in matrix_map:
            raise ValueError(f"依赖的步骤不存在: {dep}")
        resolved.extend(matrix_map[dep])
    return resolved


def parse_step(name: str, data: dict[str, Any]) -> StepNode:
    """解析单个 step"""
    # 查找 action 类型
    action_type = find_action_type(data)

    if not action_type:
        raise ValueError(
            f"step '{name}' 缺少 action 字段，"
            f"支持的 action 类型: {list_actions()}"
        )

    # 检查是否有多个 action
    found_actions = [a for a in list_actions() if a in data]
    if len(found_actions) > 1:
        raise ValueError(
            f"step '{name}' 包含多个 action: {found_actions}，只能有一个"
        )

    action = get_action(action_type)
    if action is None:
        raise ValueError(f"未注册的 action 类型: {action_type}")

    parsed_config = action.parse_config(data[action_type])

    return StepNode(
        name=name,
        action=ActionNode(type=action_type, config=parsed_config),
        depends_on=data.get("depends_on", []),
        extract=data.get("extract", {}),
        validate=parse_assertions(data.get("validate", [])),
        when=parse_when(data.get("when")),
        set_vars=data.get("set_vars", {}),
        config=data.get("config", {}),
        hooks=parse_step_hooks(data.get("hooks")),
    )


def parse_testcase(data: dict[str, Any]) -> TestCase:
    """解析整个测试用例"""
    if "version" not in data:
        raise ValueError("缺少 version 字段")

    if "steps" not in data or not data["steps"]:
        raise ValueError("缺少 steps 字段或 steps 为空")

    mode = data.get("mode", "sequential")
    if mode not in ("sequential", "parallel"):
        raise ValueError(f"不支持的执行模式: {mode}，支持: sequential, parallel")

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
                    raise ValueError(
                        f"step '{name}' 的 matrix 变量与 set_vars 重名: {sorted(conflict)}"
                    )
                step.set_vars = {**matrix_vars, **step.set_vars}

            if step.name in steps:
                raise ValueError(f"步骤名称重复: {step.name}")

            steps[step.name] = step

    for step in steps.values():
        step.depends_on = resolve_depends_on(step.depends_on, matrix_map)

    return TestCase(
        version=data["version"],
        vars=data.get("vars", {}),
        steps=steps,
        mode=mode,
        hooks=parse_testcase_hooks(data.get("hooks")),
    )


def load_testcase(path: str | Path) -> TestCase:
    """从 YAML/JSON 文件加载测试用例"""
    path = Path(path).resolve()
    data = load_file(path)
    testcase = parse_testcase(data)
    testcase.source_path = str(path)
    testcase.base_dir = str(path.parent)
    logger.info(f"解析测试用例: {path}, 包含 {len(testcase.steps)} 个步骤")
    return testcase
