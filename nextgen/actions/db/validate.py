"""DB result validation."""

from typing import Any

from nextgen.core.extract import jsonpath_value
from nextgen.core.model import AssertionNode
from nextgen.core.operators import evaluate_operator


class DbValidator:
    """DB result validator."""

    def validate(
        self,
        result: dict[str, Any],
        assertions: list[AssertionNode],
    ) -> list[str]:
        """Validate a query result.

        Supports JSONPath syntax:
        - $.row_count -> row count
        - $.rows[0].name -> row data
        - $.columns -> column names
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
                        f"{assertion.op} assertion failed: {assertion.left} "
                        f"actual={actual}, expected={expected}"
                    )
            except Exception as e:
                errors.append(f"assertion execution error: {assertion}, error: {e}")

        return errors


# Module-level convenience function.
_validator = DbValidator()


def validate_result(
    result: dict[str, Any],
    assertions: list[AssertionNode],
) -> list[str]:
    return _validator.validate(result, assertions)
