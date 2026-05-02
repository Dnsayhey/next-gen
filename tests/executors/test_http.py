"""HTTP 执行器单元测试"""

import pytest

from nextgen.core.context import Context
from nextgen.core.model import AssertionNode
from nextgen.executors.http.extract import extract_variables
from nextgen.executors.http.validate import validate_response


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
