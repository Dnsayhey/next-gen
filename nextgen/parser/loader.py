"""DSL 解析器 - 支持 YAML 和 JSON 格式"""

import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from nextgen.core.model import (
    AssertionNode,
    RequestNode,
    StepNode,
    TestCase,
)

SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json"}

# 已注册的 action 类型
SUPPORTED_ACTIONS = {"request"}


def register_action(action_type: str) -> None:
    """注册新的 action 类型"""
    SUPPORTED_ACTIONS.add(action_type)


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
    for action_type in SUPPORTED_ACTIONS:
        if action_type in data:
            return action_type
    return None


def parse_request(config: dict[str, Any]) -> None:
    """验证 request 配置"""
    if "method" not in config:
        raise ValueError("request 必须包含 method 字段")
    if "url" not in config:
        raise ValueError("request 必须包含 url 字段")

    # 检查请求体互斥
    body_fields = [f for f in ["json", "form", "multipart", "body"] if config.get(f) is not None]
    if len(body_fields) > 1:
        raise ValueError("json/form/multipart/body 不能同时出现，只能选择一种")


# Action 配置验证器注册表
ACTION_VALIDATORS = {
    "request": parse_request,
}


def register_action_validator(action_type: str, validator) -> None:
    """注册新的 action 配置验证器"""
    ACTION_VALIDATORS[action_type] = validator


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


def parse_step(name: str, data: dict[str, Any]) -> StepNode:
    """解析单个 step"""
    # 查找 action 类型
    action_type = find_action_type(data)

    if not action_type:
        raise ValueError(
            f"step '{name}' 缺少 action 字段，"
            f"支持的 action 类型: {SUPPORTED_ACTIONS}"
        )

    # 检查是否有多个 action
    found_actions = [a for a in SUPPORTED_ACTIONS if a in data]
    if len(found_actions) > 1:
        raise ValueError(
            f"step '{name}' 包含多个 action: {found_actions}，只能有一个"
        )

    action_config = data[action_type]

    # 验证 action 配置
    if action_type in ACTION_VALIDATORS:
        ACTION_VALIDATORS[action_type](action_config)

    return StepNode(
        name=name,
        action_type=action_type,
        action_config=action_config,
        depends_on=data.get("depends_on", []),
        extract=data.get("extract", {}),
        validate=parse_assertions(data.get("validate", [])),
        config=data.get("config", {}),
    )


def parse_testcase(data: dict[str, Any]) -> TestCase:
    """解析整个测试用例"""
    if "version" not in data:
        raise ValueError("缺少 version 字段")

    if "steps" not in data or not data["steps"]:
        raise ValueError("缺少 steps 字段或 steps 为空")

    steps = {}
    for name, raw in data["steps"].items():
        steps[name] = parse_step(name, raw)

    return TestCase(
        version=data["version"],
        vars=data.get("vars", {}),
        steps=steps,
    )


def load_testcase(path: str | Path) -> TestCase:
    """从 YAML/JSON 文件加载测试用例"""
    data = load_file(path)
    testcase = parse_testcase(data)
    logger.info(f"解析测试用例: {path}, 包含 {len(testcase.steps)} 个步骤")
    return testcase
