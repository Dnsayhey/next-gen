"""HTTP response JSONPath helpers."""

from __future__ import annotations

from typing import Any

from nextgen.core.extract import MISSING, extract_value, jsonpath_value, parse_extract_rule

_HTTP_META_PREFIX = "$$."


def http_extract_value(result: dict[str, Any], rule: str | dict[str, Any]) -> Any:
    """Extract a value using HTTP response path semantics."""
    if isinstance(rule, str):
        return _http_jsonpath_value(result, rule)

    if isinstance(rule, dict) and ("jsonpath" in rule or "regex" in rule):
        parsed = parse_extract_rule(rule)
        if parsed.method == "regex":
            return extract_value(result.get("body", {}), rule)
        try:
            value = _http_jsonpath_value(result, parsed.expr, default=MISSING)
        except Exception:
            if parsed.has_default:
                return parsed.default
            raise
        if value is MISSING:
            if parsed.has_default:
                return parsed.default
            return None
        return value

    return extract_value(result.get("body", {}), rule)


def http_jsonpath_value(result: dict[str, Any], expr: str) -> Any:
    """Evaluate a validation JSONPath using HTTP response path semantics."""
    return _http_jsonpath_value(result, expr)


def _http_jsonpath_value(result: dict[str, Any], expr: str, default: Any = None) -> Any:
    if expr.startswith(_HTTP_META_PREFIX):
        meta_expr = "$." + expr[len(_HTTP_META_PREFIX):]
        return jsonpath_value(_metadata_source(result), _normalize_header_path(meta_expr), default=default)
    return jsonpath_value(result.get("body", {}), expr, default=default)


def _metadata_source(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status_code": result.get("status_code"),
        "headers": _case_insensitive_headers(result.get("headers", {})),
    }


def _case_insensitive_headers(headers: Any) -> dict[str, Any]:
    if not isinstance(headers, dict):
        return {}
    return {str(key).lower(): value for key, value in headers.items()}


def _normalize_header_path(expr: str) -> str:
    if expr.startswith("$.headers."):
        return "$.headers." + expr[10:].lower()
    return expr
