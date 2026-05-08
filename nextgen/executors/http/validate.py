"""HTTP 响应验证"""

from typing import Any

from nextgen.core.extract import jsonpath_value
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
        - $.status_code → 状态码
        - $.headers.xxx → 从 HTTP 响应头提取
        - $.body.xxx → 从 body 命名空间提取
        """
        errors = []
        source = _response_source(result)

        for assertion in assertions:
            try:
                left_expr = assertion.left

                if left_expr.startswith("$.headers."):
                    left_expr = "$.headers." + left_expr[10:].lower()
                actual = jsonpath_value(source, left_expr)
                if actual is None and _is_legacy_body_path(left_expr):
                    actual = jsonpath_value(source["body"], left_expr)

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


def _response_source(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status_code": result.get("status_code"),
        "headers": _case_insensitive_headers(result.get("headers", {})),
        "body": result.get("body", {}),
    }


def _case_insensitive_headers(headers: Any) -> dict[str, Any]:
    if not isinstance(headers, dict):
        return {}
    return {str(key).lower(): value for key, value in headers.items()}


def _is_legacy_body_path(expr: Any) -> bool:
    return (
        isinstance(expr, str)
        and expr.startswith("$.")
        and not expr.startswith("$.body.")
        and not expr.startswith("$.headers.")
        and expr != "$.status_code"
    )
