"""HTTP 响应验证"""

from typing import Any

from nextgen.actions.http.path import http_jsonpath_value
from nextgen.core.model import AssertionNode
from nextgen.core.operators import evaluate_operator


class HttpValidator:
    """HTTP 响应断言器"""

    def validate(
        self,
        result: dict[str, Any],
        assertions: list[AssertionNode],
    ) -> list[str]:
        """验证 HTTP 响应

        支持 JSONPath 语法：
        - $.code → 从 body 提取
        - $$.status_code → 状态码
        - $$.headers.xxx → 从 HTTP 响应头提取
        """
        errors = []

        for assertion in assertions:
            try:
                left_expr = assertion.left
                actual = http_jsonpath_value(result, left_expr)

                expected = assertion.right

                passed = evaluate_operator(assertion.op, actual, expected)
                if not passed:
                    errors.append(
                        f"{assertion.op} 断言失败: {assertion.left} "
                        f"实际={actual}, 期望={expected}"
                    )
            except Exception as e:
                errors.append(f"断言执行错误: {assertion}, 错误: {e}")

        return errors


# 模块级便捷函数（保持向后兼容）
_validator = HttpValidator()


def validate_response(
    result: dict[str, Any],
    assertions: list[AssertionNode],
) -> list[str]:
    return _validator.validate(result, assertions)
