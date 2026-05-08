"""断言基类 - 提供通用断言方法"""

from typing import Any

from nextgen.core.operators import evaluate_operator


class BaseValidator:
    """断言基类，提供通用断言方法"""

    def evaluate(self, op: str, left: Any, right: Any) -> bool:
        """根据 op 执行断言操作。"""
        return evaluate_operator(op, left, right)

    def _assert(self, op: str, left: Any, right: Any) -> bool:
        """兼容旧调用方式。"""
        return self.evaluate(op, left, right)
