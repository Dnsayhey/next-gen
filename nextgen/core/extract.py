"""Common variable extraction utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

from nextgen.core.errors import ParseError

MISSING = object()


@dataclass(frozen=True)
class ExtractRule:
    """Variable extraction rule."""

    method: str
    expr: str
    group: int | str | None = None
    default: Any = None
    has_default: bool = False


def parse_extract_rule(raw: str | dict[str, Any]) -> ExtractRule:
    """Parse an extraction rule. String shorthand is treated as JSONPath."""
    if isinstance(raw, str):
        return ExtractRule(method="jsonpath", expr=raw)

    if not isinstance(raw, dict):
        raise ParseError(f"extract rule must be a string or dict, got {type(raw).__name__}")

    has_default = "default" in raw
    default = raw.get("default")

    if "jsonpath" in raw:
        return ExtractRule(
            method="jsonpath",
            expr=raw["jsonpath"],
            default=default,
            has_default=has_default,
        )

    if "regex" in raw:
        if "group" not in raw:
            raise ParseError("regex extract must include a group field")
        return ExtractRule(
            method="regex",
            expr=raw["regex"],
            group=raw["group"],
            default=default,
            has_default=has_default,
        )

    raise ParseError("extract rule must include jsonpath or regex")


def extract_value(source: Any, raw_rule: str | dict[str, Any]) -> Any:
    """Extract a value from source according to a rule."""
    rule = parse_extract_rule(raw_rule)

    try:
        if rule.method == "jsonpath":
            value = jsonpath_value(source, rule.expr, default=MISSING)
        elif rule.method == "regex":
            value = _extract_regex(source, rule.expr, rule.group)
        else:
            raise ParseError(f"unsupported extract method: {rule.method}")
    except Exception:
        if rule.has_default:
            return rule.default
        raise

    if value is MISSING:
        if rule.has_default:
            return rule.default
        return None
    if rule.method == "regex" and value is None and rule.has_default:
        return rule.default
    return value


def jsonpath_value(source: Any, expr: str, default: Any = None) -> Any:
    """Return the JSONPath match value, or all values when multiple paths match."""
    matches = jsonpath_parse(expr).find(source)
    if not matches:
        return default
    if len(matches) == 1:
        return matches[0].value
    return [match.value for match in matches]


def _extract_regex(source: Any, pattern: str, group: int | str | None) -> Any:
    match = re.search(pattern, _stringify_source(source))
    if not match:
        return None
    return match.group(group)


def _stringify_source(source: Any) -> str:
    if isinstance(source, str):
        return source
    return str(source)
