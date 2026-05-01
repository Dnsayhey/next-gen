"""HTTP 响应验证"""

from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

from nextgen.core.model import AssertionNode


def validate_response(
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
            # 解析左侧表达式
            left_expr = assertion.left

            if left_expr == "$.status_code":
                actual = result.get("status_code")
            elif left_expr.startswith("$.headers."):
                # 从 body 中的 headers 字段提取
                header_name = left_expr[10:]
                if isinstance(body, dict) and "headers" in body:
                    actual = body["headers"].get(header_name)
                else:
                    actual = None
            elif left_expr.startswith("$."):
                # 从 body 提取
                matches = jsonpath_parse(left_expr).find(body)
                actual = matches[0].value if matches else None
            else:
                # 直接从 body 提取
                matches = jsonpath_parse(left_expr).find(body)
                actual = matches[0].value if matches else None

            expected = assertion.right

            # 执行断言
            passed = _assert(assertion.op, actual, expected)
            if not passed:
                errors.append(
                    f"{assertion.op} 断言失败: {assertion.left} "
                    f"实际={actual}, 期望={expected}"
                )
        except Exception as e:
            errors.append(f"断言执行错误: {assertion}, 错误: {e}")

    return errors


def _assert(op: str, actual: Any, expected: Any) -> bool:
    """执行断言操作"""
    if op == "eq":
        return actual == expected
    elif op == "ne":
        return actual != expected
    elif op == "gt":
        return actual > expected
    elif op == "lt":
        return actual < expected
    elif op == "gte":
        return actual >= expected
    elif op == "lte":
        return actual <= expected
    elif op == "contains":
        return str(expected) in str(actual)
    else:
        raise ValueError(f"不支持的断言操作: {op}")
