"""HTTP action 单元测试"""

import pytest

from nextgen.core.context import Context
from nextgen.core.files import load_file_content, resolve_case_path
from nextgen.core.model import AssertionNode
from nextgen.actions.http.client import execute_request
from nextgen.actions.http.extract import extract_variables
from nextgen.actions.http.model import RequestConfig
from nextgen.actions.http.validate import validate_response


class TestRequestConfig:
    """测试 RequestConfig"""

    def test_default_values(self):
        node = RequestConfig(method="GET", url="http://test.com")
        assert node.method == "GET"
        assert node.url == "http://test.com"
        assert node.headers == {}
        assert node.params == {}
        assert node.json is None
        assert node.form is None
        assert node.multipart is None
        assert node.body is None
        assert node.content_type is None
        assert node.timeout is None

    def test_body_type_json(self):
        node = RequestConfig(method="POST", url="http://test.com", json={"key": "value"})
        assert node.body_type() == "json"

    def test_body_type_form(self):
        node = RequestConfig(method="POST", url="http://test.com", form={"key": "value"})
        assert node.body_type() == "form"

    def test_body_type_multipart(self):
        node = RequestConfig(method="POST", url="http://test.com", multipart={"file": "@./test.csv"})
        assert node.body_type() == "multipart"

    def test_body_type_raw(self):
        node = RequestConfig(method="POST", url="http://test.com", body="<xml/>")
        assert node.body_type() == "raw"

    def test_body_type_none(self):
        node = RequestConfig(method="GET", url="http://test.com")
        assert node.body_type() is None

    def test_request_config_from_dict(self):
        config = RequestConfig.from_dict({"method": "get", "url": "http://test.com"})
        assert config == RequestConfig(method="GET", url="http://test.com")
        assert config.summary() == "GET http://test.com"

    @pytest.mark.asyncio
    async def test_execute_request_includes_rendered_request_snapshot(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200
            headers = {"content-type": "application/json"}

            def json(self):
                return {"code": 0}

        class FakeClient:
            def __init__(self, timeout=None):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def request(self, **kwargs):
                captured.update(kwargs)
                return FakeResponse()

        monkeypatch.setattr("nextgen.actions.http.client.httpx.AsyncClient", FakeClient)

        request = RequestConfig(
            method="POST",
            url="${base_url}/login",
            headers={"Authorization": "Bearer ${token}"},
            params={"mobile": "${mobile}"},
            json={"password": "${password}"},
            timeout=3,
        )
        ctx = Context({
            "base_url": "https://example.com",
            "token": "abc123",
            "mobile": "13100000000",
            "password": "secret",
        })

        result = await execute_request(request, ctx)

        assert captured["url"] == "https://example.com/login"
        assert result.data == {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": {"code": 0},
        }
        assert result.action_input == {
            "type": "http",
            "method": "POST",
            "url": "https://example.com/login",
            "headers": {"Authorization": "Bearer abc123"},
            "params": {"mobile": "13100000000"},
            "body_type": "json",
            "body": {"password": "secret"},
            "timeout": 3,
        }
        assert result.action_output == {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": {"code": 0},
        }
        assert result.summary_status == 200


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
            "body": {"headers": {"X-Custom": "body-value"}},
            "headers": {"X-Custom": "header-value"},
        }
        ctx = Context()
        config = {"custom": "$.headers.X-Custom"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["custom"] == "header-value"

    def test_extract_status_code_prefers_response_metadata_over_body(self):
        result = {
            "status_code": 200,
            "body": {"status_code": 500},
            "headers": {},
        }
        ctx = Context()
        config = {"status": "$.status_code"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["status"] == 200

    def test_extract_can_use_explicit_body_namespace_for_conflicting_keys(self):
        result = {
            "status_code": 200,
            "body": {"status_code": 500, "headers": {"X-Custom": "body-value"}},
            "headers": {"X-Custom": "header-value"},
        }
        ctx = Context()
        config = {
            "body_status": "$.body.status_code",
            "body_header": "$.body.headers.X-Custom",
        }
        extracted = extract_variables(result, config, ctx)
        assert extracted["body_status"] == 500
        assert extracted["body_header"] == "body-value"

    def test_extract_multiple_jsonpath_matches(self):
        result = {
            "status_code": 200,
            "body": {"users": [{"name": "Alice"}, {"name": "Bob"}]},
            "headers": {},
        }
        ctx = Context()
        config = {"names": "$.users[*].name"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["names"] == ["Alice", "Bob"]

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

    def test_extract_with_jsonpath_object_rule(self):
        result = {
            "status_code": 200,
            "body": {"data": {"token": "abc123"}},
            "headers": {},
        }
        ctx = Context()
        config = {"token": {"jsonpath": "$.data.token"}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["token"] == "abc123"

    def test_extract_with_regex_rule(self):
        result = {
            "status_code": 200,
            "body": "csrf=abc123; session=xyz",
            "headers": {},
        }
        ctx = Context()
        config = {"csrf": {"regex": r"csrf=([a-z0-9]+)", "group": 1}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["csrf"] == "abc123"

    def test_extract_with_regex_default(self):
        result = {
            "status_code": 200,
            "body": "no token here",
            "headers": {},
        }
        ctx = Context()
        config = {
            "csrf": {
                "regex": r"csrf=([a-z0-9]+)",
                "group": 1,
                "default": "",
            }
        }
        extracted = extract_variables(result, config, ctx)
        assert extracted["csrf"] == ""

    def test_extract_failure_sets_none_consistent_with_db(self):
        result = {
            "status_code": 200,
            "body": "not json",
            "headers": {},
        }
        ctx = Context()
        config = {"bad": {"regex": r"(", "group": 1}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["bad"] is None
        assert ctx.get("bad") is None


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


class TestHttpFileUtils:
    """测试 HTTP 文件路径工具"""

    def test_resolve_relative_path_against_case_base_dir(self, tmp_path):
        assert resolve_case_path("data.txt", tmp_path) == tmp_path / "data.txt"

    def test_load_file_content_uses_case_base_dir(self, tmp_path):
        file = tmp_path / "payload.txt"
        file.write_text("hello", encoding="utf-8")

        assert load_file_content("@payload.txt", tmp_path) == "hello"

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

    def test_contains_pass_with_multiple_jsonpath_matches(self):
        result = {
            "status_code": 200,
            "body": {
                "infos": [
                    {"name": "rename_dir_EdRu2Gdk"},
                    {"name": "new_EdRu2Gdk.sh"},
                ]
            },
            "headers": {},
        }
        assertions = [
            AssertionNode(
                op="contains",
                left="$.infos[*].name",
                right="new_EdRu2Gdk.sh",
            )
        ]
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

    def test_status_code_prefers_response_metadata_over_body(self):
        result = {
            "status_code": 200,
            "body": {"status_code": 500},
            "headers": {},
        }
        assertions = [AssertionNode(op="eq", left="$.status_code", right=200)]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_headers_use_response_headers_not_body_headers(self):
        result = {
            "status_code": 200,
            "body": {"headers": {"X-Custom": "body-value"}},
            "headers": {"X-Custom": "header-value"},
        }
        assertions = [AssertionNode(op="eq", left="$.headers.X-Custom", right="header-value")]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_header_lookup_is_case_insensitive(self):
        result = {
            "status_code": 200,
            "body": {},
            "headers": {"content-type": "application/json"},
        }
        assertions = [AssertionNode(op="eq", left="$.headers.Content-Type", right="application/json")]
        errors = validate_response(result, assertions)
        assert errors == []

    def test_explicit_body_namespace_can_validate_conflicting_keys(self):
        result = {
            "status_code": 200,
            "body": {"status_code": 500},
            "headers": {},
        }
        assertions = [AssertionNode(op="eq", left="$.body.status_code", right=500)]
        errors = validate_response(result, assertions)
        assert errors == []

    @pytest.mark.parametrize(
        ("op", "left", "right"),
        [
            ("ne", "$.code", 1),
            ("gt", "$.count", 1),
            ("lt", "$.count", 3),
            ("gte", "$.count", 2),
            ("lte", "$.count", 2),
            ("not_contains", "$.message", "error"),
            ("starts_with", "$.name", "user_"),
            ("ends_with", "$.file", ".json"),
            ("in", "$.status", ["active", "pending"]),
            ("not_in", "$.role", ["banned"]),
            ("matches", "$.email", r"^[^@]+@[^@]+$"),
            ("len_eq", "$.items", 3),
            ("len_ne", "$.items", 0),
            ("len_gt", "$.items", 2),
            ("len_lt", "$.items", 4),
            ("len_gte", "$.items", 3),
            ("len_lte", "$.items", 3),
        ],
    )
    def test_extended_operators_through_http_validator(self, op, left, right):
        result = {
            "status_code": 200,
            "body": {
                "code": 0,
                "count": 2,
                "message": "success",
                "name": "user_admin",
                "file": "report.json",
                "status": "active",
                "role": "admin",
                "email": "user@example.com",
                "items": [1, 2, 3],
            },
            "headers": {},
        }
        assertions = [AssertionNode(op=op, left=left, right=right)]
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
