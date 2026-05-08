"""断言基类 - 提供通用断言方法"""

import re
from typing import Any


class BaseValidator:
    """断言基类，提供通用断言方法"""

    def eq(self, left: Any, right: Any) -> bool:
        return left == right

    def ne(self, left: Any, right: Any) -> bool:
        return left != right

    def gt(self, left: Any, right: Any) -> bool:
        return left > right

    def lt(self, left: Any, right: Any) -> bool:
        return left < right

    def gte(self, left: Any, right: Any) -> bool:
        return left >= right

    def lte(self, left: Any, right: Any) -> bool:
        return left <= right

    def contains(self, left: Any, right: Any) -> bool:
        return str(right) in str(left)

    def not_contains(self, left: Any, right: Any) -> bool:
        return str(right) not in str(left)

    def starts_with(self, left: Any, right: Any) -> bool:
        return str(left).startswith(str(right))

    def ends_with(self, left: Any, right: Any) -> bool:
        return str(left).endswith(str(right))

    def is_in(self, left: Any, right: Any) -> bool:
        try:
            return left in right
        except TypeError:
            return False

    def not_in(self, left: Any, right: Any) -> bool:
        try:
            return left not in right
        except TypeError:
            return False

    def matches(self, left: Any, right: Any) -> bool:
        return re.search(str(right), str(left)) is not None

    def len_eq(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length == right

    def len_ne(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length != right

    def len_gt(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length > right

    def len_lt(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length < right

    def len_gte(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length >= right

    def len_lte(self, left: Any, right: Any) -> bool:
        length = self._safe_len(left)
        return length is not None and length <= right

    def _safe_len(self, value: Any) -> int | None:
        try:
            return len(value)
        except TypeError:
            return None

    def _assert(self, op: str, left: Any, right: Any) -> bool:
        """根据 op 调用对应断言方法"""
        method_name = "is_in" if op == "in" else op
        method = getattr(self, method_name, None)
        if method is None:
            raise ValueError(f"不支持的断言操作: {op}")
        return method(left, right)
