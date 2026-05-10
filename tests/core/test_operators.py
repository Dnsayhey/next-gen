"""operators.py unit tests"""

import pytest

from nextgen.core.operators import evaluate_operator


class TestEvaluateOperator:
    """Test shared comparison operators"""

    @pytest.mark.parametrize(
        ("op", "left", "right", "expected"),
        [
            ("eq", 1, 1, True),
            ("ne", 1, 2, True),
            ("gt", 2, 1, True),
            ("lt", 1, 2, True),
            ("gte", 2, 2, True),
            ("lte", 2, 2, True),
            ("contains", "hello world", "world", True),
            ("not_contains", "hello world", "xyz", True),
            ("starts_with", "user_admin", "user_", True),
            ("ends_with", "report.json", ".json", True),
            ("in", "active", ["active", "pending"], True),
            ("not_in", "disabled", ["active", "pending"], True),
            ("matches", "user@example.com", r"^[^@]+@[^@]+$", True),
            ("len_eq", [1, 2, 3], 3, True),
            ("len_ne", [1, 2], 3, True),
            ("len_gt", [1, 2, 3], 2, True),
            ("len_lt", [1], 2, True),
            ("len_gte", [1, 2], 2, True),
            ("len_lte", [1, 2], 2, True),
        ],
    )
    def test_supported_operators(self, op, left, right, expected):
        assert evaluate_operator(op, left, right) is expected

    @pytest.mark.parametrize("op", ["len_eq", "len_ne", "len_gt", "len_lt", "len_gte", "len_lte"])
    def test_len_operators_return_false_for_values_without_length(self, op):
        assert evaluate_operator(op, 1, 1) is False

    def test_membership_operators_return_false_for_non_iterable_right(self):
        assert evaluate_operator("in", "a", 1) is False
        assert evaluate_operator("not_in", "a", 1) is False

    @pytest.mark.parametrize("op", ["gt", "lt", "gte", "lte"])
    def test_ordering_operators_return_false_for_incompatible_types(self, op):
        assert evaluate_operator(op, "a", 1) is False

    def test_unknown_operator(self):
        with pytest.raises(ValueError, match="unsupported operator"):
            evaluate_operator("unknown", 1, 1)
