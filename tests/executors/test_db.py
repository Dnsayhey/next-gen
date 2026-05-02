"""DB 执行器单元测试"""

import pytest

from nextgen.core.context import Context
from nextgen.core.model import AssertionNode
from nextgen.executors.db.extract import extract_variables
from nextgen.executors.db.validate import validate_result
from nextgen.executors.db.drivers import get_driver


class TestGetDriver:
    """测试 get_driver"""

    def test_postgres(self):
        driver = get_driver("postgres://localhost/test")
        assert driver.__name__ == "nextgen.executors.db.drivers.postgres"

    def test_postgresql(self):
        driver = get_driver("postgresql://localhost/test")
        assert driver.__name__ == "nextgen.executors.db.drivers.postgres"

    def test_mysql(self):
        driver = get_driver("mysql://localhost/test")
        assert driver.__name__ == "nextgen.executors.db.drivers.mysql"

    def test_sqlite(self):
        driver = get_driver("sqlite:///tmp/test.db")
        assert driver.__name__ == "nextgen.executors.db.drivers.sqlite"

    def test_unsupported(self):
        with pytest.raises(ValueError, match="不支持的数据库类型"):
            get_driver("mongodb://localhost/test")


class TestExtractVariables:
    """测试 extract_variables"""

    def test_extract_row_field(self):
        result = {
            "rows": [{"id": 1, "name": "Alice"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        ctx = Context()
        config = {"username": "$.rows[0].name"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["username"] == "Alice"
        assert ctx.get("username") == "Alice"

    def test_extract_row_count(self):
        result = {
            "rows": [{"id": 1}, {"id": 2}],
            "row_count": 2,
            "columns": ["id"],
        }
        ctx = Context()
        config = {"count": "$.row_count"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["count"] == 2

    def test_extract_missing_path(self):
        result = {
            "rows": [],
            "row_count": 0,
            "columns": [],
        }
        ctx = Context()
        config = {"value": "$.rows[0].name"}
        extracted = extract_variables(result, config, ctx)
        assert extracted["value"] is None


class TestValidateResult:
    """测试 validate_result"""

    def test_eq_pass(self):
        result = {
            "rows": [{"id": 1}],
            "row_count": 1,
            "columns": ["id"],
        }
        assertions = [AssertionNode(op="eq", left="$.row_count", right=1)]
        errors = validate_result(result, assertions)
        assert errors == []

    def test_eq_fail(self):
        result = {
            "rows": [{"id": 1}, {"id": 2}],
            "row_count": 2,
            "columns": ["id"],
        }
        assertions = [AssertionNode(op="eq", left="$.row_count", right=1)]
        errors = validate_result(result, assertions)
        assert len(errors) == 1
        assert "eq 断言失败" in errors[0]

    def test_contains_pass(self):
        result = {
            "rows": [],
            "row_count": 0,
            "columns": ["id", "name"],
        }
        assertions = [AssertionNode(op="contains", left="$.columns", right="name")]
        errors = validate_result(result, assertions)
        assert errors == []

    def test_multiple_assertions(self):
        result = {
            "rows": [{"id": 1, "name": "Alice"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        assertions = [
            AssertionNode(op="eq", left="$.row_count", right=1),
            AssertionNode(op="eq", left="$.rows[0].name", right="Alice"),
        ]
        errors = validate_result(result, assertions)
        assert errors == []
