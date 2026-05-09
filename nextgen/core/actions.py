"""Action registry."""

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
    """Complete action capability definition."""

    name: str
    parse_config: ActionParseConfig
    execute: ActionExecute
    extract: ActionExtract
    validate: ActionValidate
    summarize: ActionSummarize


ACTION_REGISTRY: dict[str, ActionSpec] = {}


def register_action(spec: ActionSpec) -> None:
    """Register a complete action definition."""
    ACTION_REGISTRY[spec.name] = spec


def get_action(name: str) -> ActionSpec | None:
    """Get an action definition."""
    return ACTION_REGISTRY.get(name)


def list_actions() -> list[str]:
    """List registered action names."""
    return list(ACTION_REGISTRY)


def snapshot_actions() -> dict[str, ActionSpec]:
    """Snapshot the action registry."""
    return dict(ACTION_REGISTRY)


def restore_actions(snapshot: dict[str, ActionSpec]) -> None:
    """Restore the action registry."""
    ACTION_REGISTRY.clear()
    ACTION_REGISTRY.update(snapshot)
