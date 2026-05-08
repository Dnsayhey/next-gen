"""变量上下文 - 管理测试执行过程中的变量"""

import re
from copy import deepcopy
from typing import Any

from loguru import logger

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PURE_VAR_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_MAX_RENDER_DEPTH = 10


class Context:
    """变量上下文

    变量作用域：局部优先（extract 覆盖全局同名变量）
    """

    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.vars: dict[str, Any] = initial or {}
        self.metadata: dict[str, Any] = metadata or {}

    def set(self, key: str, value: Any) -> None:
        """设置变量"""
        self.vars[key] = value
        logger.debug(f"设置变量: {key} = {value}")

    def get(self, key: str) -> Any | None:
        """获取变量"""
        return self.vars.get(key)

    def snapshot(self) -> dict[str, Any]:
        """获取当前上下文快照"""
        return deepcopy(self.vars)

    def derive(self, initial: dict[str, Any] | None = None) -> "Context":
        """基于当前上下文创建子上下文"""
        data = self.snapshot()
        if initial:
            data.update(initial)
        return Context(data, metadata=self.metadata)

    def merge(self, updates: dict[str, Any]) -> None:
        """批量合并变量"""
        for key, value in updates.items():
            self.set(key, value)

    def render(self, value: Any, _depth: int = 0) -> Any:
        """渲染变量替换

        支持 ${var_name} 语法
        """
        if not isinstance(value, str):
            return value

        pure_match = _PURE_VAR_PATTERN.fullmatch(value)
        if pure_match:
            key = pure_match.group(1)
            if key in self.vars:
                resolved = self.vars[key]
                if isinstance(resolved, str) and resolved != value:
                    if _depth >= _MAX_RENDER_DEPTH:
                        return resolved
                    return self.render(resolved, _depth + 1)
                return resolved

        result = value
        for _ in range(_MAX_RENDER_DEPTH):
            changed = False

            def replace(match: re.Match[str]) -> str:
                nonlocal changed
                key = match.group(1)
                if key not in self.vars:
                    return match.group(0)
                changed = True
                return str(self.vars[key])

            next_result = _VAR_PATTERN.sub(replace, result)
            result = next_result
            if not changed:
                break

        return result

    def render_value(self, value: Any) -> Any:
        """递归渲染任意 JSON-like 值。"""
        if isinstance(value, dict):
            return {k: self.render_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render_value(item) for item in value]
        return self.render(value)

    def render_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """递归渲染字典中的变量"""
        return self.render_value(data)
