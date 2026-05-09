"""DB action unit tests"""

import pytest

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError
from nextgen.core.model import AssertionNode
from nextgen.actions.db.client import execute_query
from nextgen.actions.db.extract import extract_variables
from nextgen.actions.db.model import DbConfig
from nextgen.actions.db.validate import validate_result
from nextgen.actions.db.drivers import get_driver
from nextgen.actions.db.drivers.sqlite import resolve_db_path


class TestDbConfig:
    """Test DbConfig"""

    def test_db_config_from_dict(self):
        config = DbConfig.from_dict({
            "url": "sqlite:///tmp/test.db",
            "query": "SELECT 1",
            "params": ["x"],
        })

        assert config == DbConfig(
            url="sqlite:///tmp/test.db",
            query="SELECT 1",
            params=["x"],
        )
        assert config.summary() == "sqlite: SELECT 1"

    def test_missing_url(self):
        with pytest.raises(ValueError, match="url"):
            DbConfig.from_dict({"query": "SELECT 1"})

    def test_missing_query(self):
        with pytest.raises(ValueError, match="query"):
            DbConfig.from_dict({"url": "sqlite:///tmp/test.db"})

    def test_params_must_be_list(self):
        with pytest.raises(ValueError, match="db.params must be a list"):
            DbConfig.from_dict({
                "url": "sqlite:///tmp/test.db",
                "query": "SELECT 1",
                "params": {"id": 1},
            })

    @pytest.mark.asyncio
    async def test_execute_query_includes_rendered_action_input_and_output(self, monkeypatch):
        async def fake_execute(url, query, params):
            assert url == "sqlite:///tmp/test.db"
            assert query == "SELECT * FROM users WHERE id=7"
            assert params == ["7", 1]
            return {
                "rows": [{"id": 7, "name": "Alice"}],
                "row_count": 1,
                "columns": ["id", "name"],
            }

        class FakeDriver:
            execute = staticmethod(fake_execute)

        monkeypatch.setattr("nextgen.actions.db.client.get_driver", lambda url: FakeDriver)

        config = DbConfig(
            url="${db_url}",
            query="SELECT * FROM users WHERE id=${uid}",
            params=["${uid}", 1],
        )
        ctx = Context({"db_url": "sqlite:///tmp/test.db", "uid": "7"})

        result = await execute_query(config, ctx)

        assert result.data == {
            "rows": [{"id": 7, "name": "Alice"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        assert result.action_input == {
            "type": "db",
            "url": "sqlite:///tmp/test.db",
            "query": "SELECT * FROM users WHERE id=7",
            "params": ["7", 1],
        }
        assert result.action_output == {
            "row_count": 1,
            "columns": ["id", "name"],
            "rows": [{"id": 7, "name": "Alice"}],
        }
        assert result.metric == {"label": "row_count", "value": 1}

    @pytest.mark.asyncio
    async def test_execute_query_raises_action_execution_error_with_action_input(self, monkeypatch):
        async def fake_execute(url, query, params):
            raise RuntimeError("db unavailable")

        class FakeDriver:
            execute = staticmethod(fake_execute)

        monkeypatch.setattr("nextgen.actions.db.client.get_driver", lambda url: FakeDriver)

        config = DbConfig(
            url="sqlite:///tmp/test.db",
            query="SELECT 1",
            params=[],
        )
        ctx = Context()

        with pytest.raises(ActionExecutionError) as exc_info:
            await execute_query(config, ctx)

        assert str(exc_info.value) == "db unavailable"
        assert exc_info.value.action_input == {
            "type": "db",
            "url": "sqlite:///tmp/test.db",
            "query": "SELECT 1",
            "params": [],
        }


class TestGetDriver:
    """Test get_driver"""

    def test_postgres(self):
        driver = get_driver("postgres://localhost/test")
        assert driver.__name__ == "nextgen.actions.db.drivers.postgres"

    def test_postgresql(self):
        driver = get_driver("postgresql://localhost/test")
        assert driver.__name__ == "nextgen.actions.db.drivers.postgres"

    def test_mysql(self):
        driver = get_driver("mysql://localhost/test")
        assert driver.__name__ == "nextgen.actions.db.drivers.mysql"

    def test_sqlite(self):
        driver = get_driver("sqlite:///tmp/test.db")
        assert driver.__name__ == "nextgen.actions.db.drivers.sqlite"

    def test_unsupported(self):
        with pytest.raises(ValueError, match="unsupported database type"):
            get_driver("mongodb://localhost/test")


class TestSqliteDriver:
    """Test SQLite URL path resolution"""

    def test_resolve_absolute_path(self):
        assert resolve_db_path("sqlite:///tmp/test.db") == "/tmp/test.db"

    def test_resolve_relative_path(self):
        assert resolve_db_path("sqlite://./examples/test.db") == "examples/test.db"


class TestExtractVariables:
    """Test extract_variables"""

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

    def test_extract_failure_sets_none_and_clears_old_context_value(self):
        result = {
            "rows": [{"id": 1}],
            "row_count": 1,
            "columns": ["id"],
        }
        ctx = Context({"value": "old"})
        config = {"value": {"regex": r"(", "group": 1}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["value"] is None
        assert ctx.get("value") is None

    def test_extract_with_jsonpath_object_rule(self):
        result = {
            "rows": [{"id": 1, "name": "Alice"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        ctx = Context()
        config = {"username": {"jsonpath": "$.rows[0].name"}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["username"] == "Alice"

    def test_extract_with_regex_rule(self):
        result = {
            "rows": [{"id": 1, "name": "Alice"}],
            "row_count": 1,
            "columns": ["id", "name"],
        }
        ctx = Context()
        config = {"username": {"regex": r"name': '([A-Za-z]+)'", "group": 1}}
        extracted = extract_variables(result, config, ctx)
        assert extracted["username"] == "Alice"


class TestValidateResult:
    """Test validate_result"""

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
        assert "eq assertion failed" in errors[0]

    def test_contains_pass(self):
        result = {
            "rows": [],
            "row_count": 0,
            "columns": ["id", "name"],
        }
        assertions = [AssertionNode(op="contains", left="$.columns", right="name")]
        errors = validate_result(result, assertions)
        assert errors == []

    def test_contains_pass_with_multiple_jsonpath_matches(self):
        result = {
            "rows": [{"name": "Alice"}, {"name": "Bob"}],
            "row_count": 2,
            "columns": ["name"],
        }
        assertions = [AssertionNode(op="contains", left="$.rows[*].name", right="Bob")]
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
