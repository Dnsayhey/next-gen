"""assertion.py 单元测试"""

import pytest

from nextgen.core.assertion import BaseValidator


class TestBaseValidator:
    """测试 BaseValidator._assert 断言方法"""

    def setup_method(self):
        self.validator = BaseValidator()

    def test_eq(self):
        assert self.validator._assert("eq", 0, 0) is True
        assert self.validator._assert("eq", 0, 1) is False

    def test_ne(self):
        assert self.validator._assert("ne", 0, 1) is True
        assert self.validator._assert("ne", 0, 0) is False

    def test_gt(self):
        assert self.validator._assert("gt", 2, 1) is True
        assert self.validator._assert("gt", 1, 1) is False
        assert self.validator._assert("gt", 1, 2) is False

    def test_lt(self):
        assert self.validator._assert("lt", 1, 2) is True
        assert self.validator._assert("lt", 1, 1) is False
        assert self.validator._assert("lt", 2, 1) is False

    def test_gte(self):
        assert self.validator._assert("gte", 2, 1) is True
        assert self.validator._assert("gte", 1, 1) is True
        assert self.validator._assert("gte", 1, 2) is False

    def test_lte(self):
        assert self.validator._assert("lte", 1, 2) is True
        assert self.validator._assert("lte", 1, 1) is True
        assert self.validator._assert("lte", 2, 1) is False

    def test_contains(self):
        assert self.validator._assert("contains", "hello world", "world") is True
        assert self.validator._assert("contains", "hello world", "xyz") is False

    @pytest.mark.parametrize(
        ("op", "left", "right", "expected"),
        [
            ("not_contains", "hello world", "xyz", True),
            ("not_contains", "hello world", "world", False),
            ("starts_with", "user_admin", "user_", True),
            ("starts_with", "admin_user", "user_", False),
            ("ends_with", "report.json", ".json", True),
            ("ends_with", "report.txt", ".json", False),
            ("in", "active", ["active", "pending"], True),
            ("in", "disabled", ["active", "pending"], False),
            ("not_in", "disabled", ["active", "pending"], True),
            ("not_in", "active", ["active", "pending"], False),
            ("matches", "user@example.com", r"^[^@]+@[^@]+$", True),
            ("matches", "not-an-email", r"^[^@]+@[^@]+$", False),
            ("len_eq", [1, 2, 3], 3, True),
            ("len_eq", [1, 2], 3, False),
            ("len_ne", [1, 2], 3, True),
            ("len_ne", [1, 2, 3], 3, False),
            ("len_gt", [1, 2, 3], 2, True),
            ("len_gt", [1, 2], 2, False),
            ("len_lt", [1], 2, True),
            ("len_lt", [1, 2], 2, False),
            ("len_gte", [1, 2], 2, True),
            ("len_gte", [1], 2, False),
            ("len_lte", [1, 2], 2, True),
            ("len_lte", [1, 2, 3], 2, False),
        ],
    )
    def test_extended_assertions(self, op, left, right, expected):
        assert self.validator._assert(op, left, right) is expected

    def test_len_assertion_fails_for_value_without_length(self):
        assert self.validator._assert("len_eq", 1, 1) is False

    def test_unknown_op(self):
        with pytest.raises(ValueError, match="不支持的断言操作"):
            self.validator._assert("unknown", 1, 1)
