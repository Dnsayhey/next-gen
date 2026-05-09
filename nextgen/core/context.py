"""Variable context for test execution."""

import re
from copy import deepcopy
from typing import Any

from loguru import logger

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PURE_VAR_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_MAX_RENDER_DEPTH = 10


class Context:
    """Variable context.

    Variable scope: local values take precedence over global values.
    """

    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.vars: dict[str, Any] = initial or {}
        self.metadata: dict[str, Any] = metadata or {}

    def set(self, key: str, value: Any) -> None:
        """Set a variable."""
        self.vars[key] = value
        logger.debug(f"Set variable: {key} = {value}")

    def get(self, key: str) -> Any | None:
        """Get a variable."""
        return self.vars.get(key)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current context."""
        return deepcopy(self.vars)

    def derive(self, initial: dict[str, Any] | None = None) -> "Context":
        """Create a child context from the current context."""
        data = self.snapshot()
        if initial:
            data.update(initial)
        return Context(data, metadata=self.metadata)

    def merge(self, updates: dict[str, Any]) -> None:
        """Merge variables in bulk."""
        for key, value in updates.items():
            self.set(key, value)

    def render(self, value: Any, _depth: int = 0) -> Any:
        """Render variable substitutions.

        Supports ${var_name} syntax.
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
        """Recursively render any JSON-like value."""
        if isinstance(value, dict):
            return {k: self.render_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render_value(item) for item in value]
        return self.render(value)

    def render_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively render variables in a dictionary."""
        return self.render_value(data)
