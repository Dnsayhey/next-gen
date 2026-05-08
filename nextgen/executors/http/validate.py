"""HTTP 响应验证"""

from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

from nextgen.core.assertion import BaseValidator
from nextgen.core.model import AssertionNode


def _jsonpath_value(data: Any, expr: str) -> Any:
    matches = jsonpath_parse(expr).find(data)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].value
    return [match.value for match in matches]


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
        - $.headers.xxx → 从 HTTP 响应头提取
        - $.body.xxx → 从 body 命名空间提取
        """
        errors = []
        body = result.get("body", {})
        headers = result.get("headers", {})

        for assertion in assertions:
            try:
                left_expr = assertion.left

                if left_expr == "$.status_code":
                    actual = result.get("status_code")
                elif left_expr.startswith("$.headers."):
                    header_name = left_expr[10:]
                    actual = _header_value(headers, header_name)
                elif left_expr.startswith("$.body."):
                    actual = _jsonpath_value(body, "$." + left_expr[7:])
                elif left_expr.startswith("$."):
                    actual = _jsonpath_value(body, left_expr)
                else:
                    actual = _jsonpath_value(body, left_expr)

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


def _header_value(headers: Any, name: str) -> Any:
    if not isinstance(headers, dict):
        return None
    if name in headers:
        return headers[name]
    lower_name = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lower_name:
            return value
    return None
