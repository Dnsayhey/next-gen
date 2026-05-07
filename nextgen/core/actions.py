"""Action 注册表"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from nextgen.core.context import Context
from nextgen.core.model import AssertionNode

ActionExecute = Callable[[dict[str, Any], Context], Awaitable[dict[str, Any]]]
ActionExtract = Callable[[dict[str, Any], dict[str, str], Context], dict[str, Any]]
ActionValidate = Callable[[dict[str, Any], list[AssertionNode]], list[str]]
ActionConfigValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ActionSpec:
    """完整 action 能力定义"""

    name: str
    execute: ActionExecute
    extract: ActionExtract
    validate: ActionValidate
    validate_config: ActionConfigValidator | None = None


ACTION_REGISTRY: dict[str, ActionSpec] = {}


def register_action(spec: ActionSpec) -> None:
    """注册完整 action 定义"""
    ACTION_REGISTRY[spec.name] = spec


def get_action(name: str) -> ActionSpec | None:
    """获取 action 定义"""
    return ACTION_REGISTRY.get(name)


def list_actions() -> list[str]:
    """列出已注册 action 名称"""
    return list(ACTION_REGISTRY)


def snapshot_actions() -> dict[str, ActionSpec]:
    """获取 action 注册表快照"""
    return dict(ACTION_REGISTRY)


def restore_actions(snapshot: dict[str, ActionSpec]) -> None:
    """恢复 action 注册表"""
    ACTION_REGISTRY.clear()
    ACTION_REGISTRY.update(snapshot)
