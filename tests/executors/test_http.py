"""HTTP 执行器单元测试"""

import pytest

from nextgen.core.context import Context
from nextgen.core.model import AssertionNode
from nextgen.executors.http.extract import extract_variables
from nextgen.executors.http.validate import validate_response, _assert


class TestAssert:
    """测试 _assert 断言函数"""

    def test_eq(self):
        assert _assert("eq", 0, 0) is True
        assert _assert("eq", 0, 1) is False

    def test_ne(self):
        assert _assert("ne", 0, 1) is True
        assert _assert("ne", 0, 0) is False

    def test_gt(self):
        assert _assert("gt", 2, 1) is True
        assert _assert("gt", 1, 1) is False
        assert _assert("gt", 1, 2) is False

    def test_lt(self):
        assert _assert("lt", 1, 2) is True
        assert _assert("lt", 1, 1) is False
        assert _assert("lt", 2, 1) is False

    def test_gte(self):
        assert _assert("gte", 2, 1) is True
        assert _assert("gte", 1, 1) is True
        assert _assert("gte", 1, 2) is False

    def test_lte(self):
        assert _assert("lte", 1, 2) is True
        assert _assert("lte", 1, 1) is True
        assert _assert("lte", 2, 1) is False

    def test_contains(self):
        assert _assert("contains", "hello world", "world") is True
        assert _assert("contains", "hello world", "xyz") is False

    def test_unknown_op(self):
        with pytest.raises(ValueError, match="不支持的断言操作"):
            _assert("unknown", 1, 1)


class TestExtractVariables:
    """测试 extract_variables"""

    def test_extract_from_body(self):
        result = {
            "status_code": 200,
            "body": {"data": {"token": "abc123"}},
            "headers": {},
        }
        ctx = Context()
        config = {"token": "$.data.token"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["token"] == "abc123"
        assert ctx.get("token") == "abc123"

    def test_extract_status_code(self):
        result = {
            "status_code": 200,
            "body": {},
            "headers": {},
        }
        ctx = Context()
        config = {"status": "$.status_code"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["status"] == 200

    def test_extract_from_body_headers(self):
        result = {
            "status_code": 200,
            "body": {"headers": {"X-Custom": "value"}},
            "headers": {},
        }
        ctx = Context()
        config = {"custom": "$.headers.X-Custom"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["custom"] == "value"

    def test_extract_missing_path(self):
        result = {
            "status_code": 200,
            "body": {"data": {}},
            "headers": {},
        }
        ctx = Context()
        config = {"token": "$.data.token"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["token"] is None


class TestValidateResponse:
    """测试 validate_response"""

    def test_eq_pass(self):
        result = {
            "status_code": 200,
            "body": {"code": 0},
            "headers": {},
        }
        assertions = [AssertionNode(op="eq", left="$.code", right=0)]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_eq_fail(self):
        result = {
            "status_code": 200,
            "body": {"code": 1},
            "headers": {},
        }
        assertions = [AssertionNode(op="eq", left="$.code", right=0)]
        errors = validate_response(result, assertions)
        assert len(errors) == 1
        assert "eq 断言失败" in errors[0]

    def test_contains_pass(self):
        result = {
            "status_code": 200,
            "body": {"message": "success"},
            "headers": {},
        }
        assertions = [AssertionNode(op="contains", left="$.message", right="success")]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_status_code(self):
        result = {
            "status_code": 200,
            "body": {},
            "headers": {},
        }
        assertions = [AssertionNode(op="eq", left="$.status_code", right=200)]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_multiple_assertions(self):
        result = {
            "status_code": 200,
            "body": {"code": 0, "message": "success"},
            "headers": {},
        }
        assertions = [
            AssertionNode(op="eq", left="$.code", right=0),
            AssertionNode(op="eq", left="$.message", right="success"),
        ]
        errors = validate_response(result, assertions)
        assert errors == []
