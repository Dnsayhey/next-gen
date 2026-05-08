"""Action 注册表"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from nextgen.core.context import Context
from nextgen.core.model import AssertionNode
from nextgen.core.result import ActionResult

ActionParseConfig = Callable[[dict[str, Any]], Any]
ActionExecute = Callable[[Any, Context], Awaitable[ActionResult]]
ActionExtract = Callable[[dict[str, Any], dict[str, Any], Context], dict[str, Any]]
ActionValidate = Callable[[dict[str, Any], list[AssertionNode]], list[str]]
ActionSummarize = Callable[[Any], str]


@dataclass(frozen=True)
class ActionSpec:
    """完整 action 能力定义"""

    name: str
    parse_config: ActionParseConfig
    execute: ActionExecute
    extract: ActionExtract
    validate: ActionValidate
    summarize: ActionSummarize


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
