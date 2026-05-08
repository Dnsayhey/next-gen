"""共享比较操作符"""

from __future__ import annotations

import re
from typing import Any, Callable


def _safe_len(value: Any) -> int | None:
    try:
        return len(value)
    except TypeError:
        return None


def _op_eq(left: Any, right: Any) -> bool:
    return left == right


def _op_ne(left: Any, right: Any) -> bool:
    return left != right


def _op_gt(left: Any, right: Any) -> bool:
    return left > right


def _op_lt(left: Any, right: Any) -> bool:
    return left < right


def _op_gte(left: Any, right: Any) -> bool:
    return left >= right


def _op_lte(left: Any, right: Any) -> bool:
    return left <= right


def _op_contains(left: Any, right: Any) -> bool:
    return str(right) in str(left)


def _op_not_contains(left: Any, right: Any) -> bool:
    return str(right) not in str(left)


def _op_starts_with(left: Any, right: Any) -> bool:
    return str(left).startswith(str(right))


def _op_ends_with(left: Any, right: Any) -> bool:
    return str(left).endswith(str(right))


def _op_in(left: Any, right: Any) -> bool:
    try:
        return left in right
    except TypeError:
        return False


def _op_not_in(left: Any, right: Any) -> bool:
    try:
        return left not in right
    except TypeError:
        return False


def _op_matches(left: Any, right: Any) -> bool:
    return re.search(str(right), str(left)) is not None


def _op_len_eq(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length == right


def _op_len_ne(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length != right


def _op_len_gt(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length > right


def _op_len_lt(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length < right


def _op_len_gte(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length >= right


def _op_len_lte(left: Any, right: Any) -> bool:
    length = _safe_len(left)
    return length is not None and length <= right


_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": _op_eq,
    "ne": _op_ne,
    "gt": _op_gt,
    "lt": _op_lt,
    "gte": _op_gte,
    "lte": _op_lte,
    "contains": _op_contains,
    "not_contains": _op_not_contains,
    "starts_with": _op_starts_with,
    "ends_with": _op_ends_with,
    "in": _op_in,
    "not_in": _op_not_in,
    "matches": _op_matches,
    "len_eq": _op_len_eq,
    "len_ne": _op_len_ne,
    "len_gt": _op_len_gt,
    "len_lt": _op_len_lt,
    "len_gte": _op_len_gte,
    "len_lte": _op_len_lte,
}


def evaluate_operator(op: str, left: Any, right: Any) -> bool:
    """执行共享比较操作符。"""
    operator = _OPERATORS.get(op)
    if operator is None:
        raise ValueError(f"不支持的操作符: {op}")
    return operator(left, right)
