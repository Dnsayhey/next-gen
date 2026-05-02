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

    def test_unknown_op(self):
        with pytest.raises(ValueError, match="不支持的断言操作"):
            self.validator._assert("unknown", 1, 1)
