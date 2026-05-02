"""断言基类 - 提供通用断言方法"""

from typing import Any


class BaseValidator:
    """断言基类，提供 eq / ne / gt / lt / gte / lte / contains 等基础方法"""

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

    def _assert(self, op: str, left: Any, right: Any) -> bool:
        """根据 op 调用对应断言方法"""
        method = getattr(self, op, None)
        if method is None:
            raise ValueError(f"不支持的断言操作: {op}")
        return method(left, right)
