"""DB 结果验证"""

from typing import Any

from nextgen.core.extract import jsonpath_value
from nextgen.core.model import AssertionNode
from nextgen.core.operators import evaluate_operator


class DbValidator:
    """DB 结果断言器"""

    def validate(
        self,
        result: dict[str, Any],
        assertions: list[AssertionNode],
    ) -> list[str]:
        """验证查询结果

        支持 JSONPath 语法：
        - $.row_count → 行数
        - $.rows[0].name → 行数据
        - $.columns → 列名列表
        """
        errors = []

        for assertion in assertions:
            try:
                left_expr = assertion.left

                actual = jsonpath_value(result, left_expr)

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


# 模块级便捷函数
_validator = DbValidator()


def validate_result(
    result: dict[str, Any],
    assertions: list[AssertionNode],
) -> list[str]:
    return _validator.validate(result, assertions)
