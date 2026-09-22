"""HTTP response validation."""

from typing import Any

from nextgen.actions.http.path import http_jsonpath_value
from nextgen.core.model import AssertionNode
from nextgen.core.operators import evaluate_operator


class HttpValidator:
    """HTTP response validator."""

    def validate(
        self,
        result: dict[str, Any],
        assertions: list[AssertionNode],
    ) -> list[str]:
        """Validate an HTTP response.

        Supports HTTP response path syntax:
        - $.code -> read ``code`` from the response body
        - $$.status_code -> status code metadata
        - $$.headers.xxx -> HTTP response header metadata

        The ``$.`` root is the response body root; ``body`` is not an
        additional path segment. Use ``$$.`` for response metadata.
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
                        f"{assertion.op} assertion failed: {assertion.left} "
                        f"actual={actual}, expected={expected}"
                    )
            except Exception as e:
                errors.append(f"assertion execution error: {assertion}, error: {e}")

        return errors


# Module-level convenience function kept for compatibility.
_validator = HttpValidator()


def validate_response(
    result: dict[str, Any],
    assertions: list[AssertionNode],
) -> list[str]:
    return _validator.validate(result, assertions)
