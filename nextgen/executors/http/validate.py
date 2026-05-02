"""HTTP 响应验证"""

from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

from nextgen.core.assertion import BaseValidator
from nextgen.core.model import AssertionNode


class HttpValidator(BaseValidator):
    """HTTP 响应断言器"""

    def validate(
        self,
        result: dict[str, Any],
        assertions: list[AssertionNode],
    ) -> list[str]:
        """验证 HTTP 响应

        支持 JSONPath 语法：
        - $.code → 从 body 提取
        - $.status_code → 状态码
        - $.headers.xxx → 从 body 中的 headers 字段提取
        """
        errors = []
        body = result.get("body", {})

        for assertion in assertions:
            try:
                left_expr = assertion.left

                if left_expr == "$.status_code":
                    actual = result.get("status_code")
                elif left_expr.startswith("$.headers."):
                    header_name = left_expr[10:]
                    if isinstance(body, dict) and "headers" in body:
                        actual = body["headers"].get(header_name)
                    else:
                        actual = None
                elif left_expr.startswith("$."):
                    matches = jsonpath_parse(left_expr).find(body)
                    actual = matches[0].value if matches else None
                else:
                    matches = jsonpath_parse(left_expr).find(body)
                    actual = matches[0].value if matches else None

                expected = assertion.right

                passed = self._assert(assertion.op, actual, expected)
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
