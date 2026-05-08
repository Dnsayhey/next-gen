"""通用变量提取工具"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse


@dataclass(frozen=True)
class ExtractRule:
    """变量提取规则"""

    method: str
    expr: str
    group: int | str | None = None
    default: Any = None
    has_default: bool = False


def parse_extract_rule(raw: str | dict[str, Any]) -> ExtractRule:
    """解析提取规则，字符串简写按 JSONPath 处理"""
    if isinstance(raw, str):
        return ExtractRule(method="jsonpath", expr=raw)

    if not isinstance(raw, dict):
        raise ValueError(f"extract 规则必须是字符串或 dict，得到 {type(raw).__name__}")

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
            raise ValueError("regex extract 必须包含 group 字段")
        return ExtractRule(
            method="regex",
            expr=raw["regex"],
            group=raw["group"],
            default=default,
            has_default=has_default,
        )

    raise ValueError("extract 规则必须包含 jsonpath 或 regex")


def extract_value(source: Any, raw_rule: str | dict[str, Any]) -> Any:
    """从 source 中按规则提取值"""
    rule = parse_extract_rule(raw_rule)

    try:
        if rule.method == "jsonpath":
            value = _extract_jsonpath(source, rule.expr)
        elif rule.method == "regex":
            value = _extract_regex(source, rule.expr, rule.group)
        else:
            raise ValueError(f"不支持的 extract 方法: {rule.method}")
    except Exception:
        if rule.has_default:
            return rule.default
        raise

    if value is None and rule.has_default:
        return rule.default
    return value


def _extract_jsonpath(source: Any, expr: str) -> Any:
    matches = jsonpath_parse(expr).find(source)
    if not matches:
        return None
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
