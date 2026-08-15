"""DB action unit tests"""

import asyncio

import pytest

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError
from nextgen.core.model import AssertionNode
from nextgen.actions.db.client import execute_query
from nextgen.actions.db.extract import extract_variables
from nextgen.actions.db.model import DbConfig
from nextgen.actions.db.validate import validate_result
from nextgen.actions.db.drivers import get_driver
from nextgen.actions.db.drivers import mysql
from nextgen.actions.db.drivers import postgres
from nextgen.actions.db.drivers import sqlite
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

    @pytest.mark.parametrize(
        ("config", "message"),
        [
            ({"url": 123, "query": "SELECT 1"}, "db.url must be a non-empty string"),
            ({"url": "sqlite:///tmp/test.db", "query": []}, "db.query must be a non-empty string"),
        ],
    )
    def test_url_and_query_must_be_non_empty_strings(self, config, message):
        with pytest.raises(ValueError, match=message):
            DbConfig.from_dict(config)

    @pytest.mark.asyncio
    async def test_execute_query_includes_rendered_action_input_and_output(self, monkeypatch):
        class FakeResource:
            async def execute(self, query, params):
                assert query == "SELECT * FROM users WHERE id=7"
                assert params == ["7", 1]
                return {
                    "rows": [{"id": 7, "name": "Alice"}],
                    "row_count": 1,
                    "columns": ["id", "name"],
                }

        class FakeDriver:
            @staticmethod
            async def create_resource(url, max_size):
                assert url == "sqlite:///tmp/test.db"
                assert max_size == 3
                return FakeResource()

        monkeypatch.setattr("nextgen.actions.db.client.get_driver", lambda url: FakeDriver)

        config = DbConfig(
            url="${db_url}",
            query="SELECT * FROM users WHERE id=${uid}",
            params=["${uid}", 1],
        )
        ctx = Context(
            {"db_url": "sqlite:///tmp/test.db", "uid": "7"},
            metadata={"max_concurrency": 3},
        )

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
        class FakeResource:
            async def execute(self, query, params):
                raise RuntimeError("db unavailable")

        class FakeDriver:
            @staticmethod
            async def create_resource(url, max_size):
                return FakeResource()

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

    @pytest.mark.asyncio
    async def test_execute_query_reuses_resource_for_same_url_and_closes_it_with_context(
        self,
        monkeypatch,
    ):
        created = []

        class FakeResource:
            def __init__(self, url):
                self.url = url
                self.queries = []
                self.closed = False

            async def execute(self, query, params):
                self.queries.append((query, params))
                return {"rows": [], "row_count": 0, "columns": []}

            async def aclose(self):
                self.closed = True

        class FakeDriver:
            @staticmethod
            async def create_resource(url, max_size):
                await asyncio.sleep(0)
                resource = FakeResource(url)
                created.append(resource)
                return resource

        monkeypatch.setattr("nextgen.actions.db.client.get_driver", lambda url: FakeDriver)
        ctx = Context(metadata={"max_concurrency": 4})
        config = DbConfig(
            url="postgres://db.example.com/app",
            query="SELECT 1",
        )

        await asyncio.gather(
            execute_query(config, ctx.derive()),
            execute_query(config, ctx.derive()),
        )

        assert len(created) == 1
        assert created[0].queries == [("SELECT 1", []), ("SELECT 1", [])]

        await ctx.close_resources()

        assert created[0].closed is True

    @pytest.mark.asyncio
    async def test_execute_query_separates_resources_by_url_and_testcase(self, monkeypatch):
        created = []

        class FakeResource:
            def __init__(self, url):
                self.url = url

            async def execute(self, query, params):
                return {"rows": [], "row_count": 0, "columns": []}

            async def aclose(self):
                pass

        class FakeDriver:
            @staticmethod
            async def create_resource(url, max_size):
                resource = FakeResource(url)
                created.append(resource)
                return resource

        monkeypatch.setattr("nextgen.actions.db.client.get_driver", lambda url: FakeDriver)
        first_case = Context()
        second_case = Context()

        await execute_query(
            DbConfig(url="postgres://db.example.com/one", query="SELECT 1"),
            first_case,
        )
        await execute_query(
            DbConfig(url="postgres://db.example.com/two", query="SELECT 1"),
            first_case,
        )
        await execute_query(
            DbConfig(url="postgres://db.example.com/one", query="SELECT 1"),
            second_case,
        )

        assert [resource.url for resource in created] == [
            "postgres://db.example.com/one",
            "postgres://db.example.com/two",
            "postgres://db.example.com/one",
        ]


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


class TestPostgresDriver:
    """Test PostgreSQL pooled resource behavior."""

    @pytest.mark.asyncio
    async def test_pool_is_reused_and_closed_explicitly(self, monkeypatch):
        events = []
        messages = []

        class FakeConnection:
            async def fetch(self, query, *params):
                events.append(("fetch", query, params))
                return [{"id": params[0]}]

        class AcquireConnection:
            async def __aenter__(self):
                events.append("acquire")
                return FakeConnection()

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("release")

        class FakePool:
            def acquire(self):
                return AcquireConnection()

            async def close(self):
                events.append("pool_close")

        async def fake_create_pool(dsn, *, min_size, max_size):
            events.append(("create_pool", dsn, min_size, max_size))
            return FakePool()

        monkeypatch.setattr(postgres.asyncpg, "create_pool", fake_create_pool)
        monkeypatch.setattr(postgres.logger, "debug", messages.append)

        resource = await postgres.create_resource(
            "postgres://user:secret@db.example.com:15432/app",
            max_size=3,
        )
        result = await resource.execute("SELECT * FROM users WHERE id = $1", [7])
        await resource.aclose()

        assert result == {
            "rows": [{"id": 7}],
            "row_count": 1,
            "columns": ["id"],
        }
        assert events == [
            (
                "create_pool",
                "postgres://user:secret@db.example.com:15432/app",
                1,
                3,
            ),
            "acquire",
            ("fetch", "SELECT * FROM users WHERE id = $1", (7,)),
            "release",
            "pool_close",
        ]
        assert messages == ["Connecting to PostgreSQL: db.example.com:15432/app"]
        assert "secret" not in messages[0]
        assert "user" not in messages[0]


class TestMysqlDriver:
    """Test MySQL pooled resource and transaction behavior."""

    @pytest.mark.asyncio
    async def test_successful_query_commits_and_releases_connection(self, monkeypatch):
        events = []
        captured_config = {}

        class FakeCursor:
            description = None
            rowcount = 1

            async def __aenter__(self):
                events.append("cursor_enter")
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("cursor_exit")

            async def execute(self, query, params):
                events.append(("execute", query, params))

            async def fetchall(self):
                events.append("fetchall")
                return []

        class FakeConnection:
            def cursor(self, cursor_class):
                assert cursor_class is mysql.aiomysql.DictCursor
                return FakeCursor()

            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

        class AcquireConnection:
            async def __aenter__(self):
                events.append("acquire")
                return FakeConnection()

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("release")

        class FakePool:
            def acquire(self):
                return AcquireConnection()

            def close(self):
                events.append("pool_close")

            async def wait_closed(self):
                events.append("pool_wait_closed")

        async def fake_create_pool(**config):
            captured_config.update(config)
            return FakePool()

        monkeypatch.setattr(mysql.aiomysql, "create_pool", fake_create_pool)

        resource = await mysql.create_resource(
            "mysql://user:secret@db.example.com/app",
            max_size=4,
        )
        result = await resource.execute(
            "UPDATE users SET active = 1 WHERE id = %s",
            [7],
        )
        await resource.aclose()

        assert result == {"rows": [], "row_count": 1, "columns": []}
        assert captured_config == {
            "host": "db.example.com",
            "port": 3306,
            "user": "user",
            "password": "secret",
            "db": "app",
            "minsize": 1,
            "maxsize": 4,
        }
        assert events == [
            "acquire",
            "cursor_enter",
            ("execute", "UPDATE users SET active = 1 WHERE id = %s", [7]),
            "fetchall",
            "cursor_exit",
            "commit",
            "release",
            "pool_close",
            "pool_wait_closed",
        ]

    @pytest.mark.asyncio
    async def test_failed_query_rolls_back_before_releasing_connection(self, monkeypatch):
        events = []

        class FakeCursor:
            async def __aenter__(self):
                events.append("cursor_enter")
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("cursor_exit")

            async def execute(self, query, params):
                events.append("execute")
                raise RuntimeError("query failed")

        class FakeConnection:
            def cursor(self, cursor_class):
                return FakeCursor()

            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

        class AcquireConnection:
            async def __aenter__(self):
                events.append("acquire")
                return FakeConnection()

            async def __aexit__(self, exc_type, exc, traceback):
                events.append("release")

        class FakePool:
            def acquire(self):
                return AcquireConnection()

            def close(self):
                events.append("pool_close")

            async def wait_closed(self):
                events.append("pool_wait_closed")

        async def fake_create_pool(**config):
            return FakePool()

        monkeypatch.setattr(mysql.aiomysql, "create_pool", fake_create_pool)

        resource = await mysql.create_resource(
            "mysql://user:secret@db.example.com/app",
            max_size=2,
        )

        with pytest.raises(RuntimeError, match="query failed"):
            await resource.execute(
                "UPDATE users SET active = 1",
                None,
            )

        assert events == [
            "acquire",
            "cursor_enter",
            "execute",
            "cursor_exit",
            "rollback",
            "release",
        ]


class TestSqliteDriver:
    """Test SQLite URL paths and case-scoped connection behavior."""

    def test_resolve_absolute_path(self):
        assert resolve_db_path("sqlite:///tmp/test.db") == "/tmp/test.db"

    def test_resolve_relative_path(self):
        assert resolve_db_path("sqlite://./examples/test.db") == "examples/test.db"

    @pytest.mark.asyncio
    async def test_resource_reuses_connection_serializes_queries_and_closes_explicitly(
        self,
        monkeypatch,
    ):
        events = []
        active_queries = 0
        max_active_queries = 0

        class FakeCursor:
            description = [("value",)]
            rowcount = -1

            def __init__(self, value):
                self.value = value

            async def fetchall(self):
                return [{"value": self.value}]

            async def close(self):
                events.append(("cursor_close", self.value))

        class FakeConnection:
            row_factory = None

            async def execute(self, query, params):
                nonlocal active_queries, max_active_queries
                active_queries += 1
                max_active_queries = max(max_active_queries, active_queries)
                events.append(("execute", query, params))
                await asyncio.sleep(0)
                active_queries -= 1
                return FakeCursor(params[0])

            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

            async def close(self):
                events.append("connection_close")

        connection = FakeConnection()
        connect_calls = []

        async def fake_connect(path):
            connect_calls.append(path)
            return connection

        monkeypatch.setattr(sqlite.aiosqlite, "connect", fake_connect)

        resource = await sqlite.create_resource(
            "sqlite://./examples/test.db",
            max_size=5,
        )
        first, second = await asyncio.gather(
            resource.execute("SELECT ? AS value", [1]),
            resource.execute("SELECT ? AS value", [2]),
        )

        assert first["rows"] == [{"value": 1}]
        assert second["rows"] == [{"value": 2}]
        assert connect_calls == ["examples/test.db"]
        assert max_active_queries == 1
        assert events == [
            ("execute", "SELECT ? AS value", [1]),
            "commit",
            ("cursor_close", 1),
            ("execute", "SELECT ? AS value", [2]),
            "commit",
            ("cursor_close", 2),
        ]

        await resource.aclose()

        assert events[-1] == "connection_close"

    @pytest.mark.asyncio
    async def test_failed_query_rolls_back_without_closing_case_connection(self, monkeypatch):
        events = []

        class FakeConnection:
            row_factory = None

            async def execute(self, query, params):
                raise RuntimeError("query failed")

            async def commit(self):
                events.append("commit")

            async def rollback(self):
                events.append("rollback")

            async def close(self):
                events.append("connection_close")

        async def fake_connect(path):
            return FakeConnection()

        monkeypatch.setattr(sqlite.aiosqlite, "connect", fake_connect)

        resource = await sqlite.create_resource("sqlite://./test.db", max_size=1)

        with pytest.raises(RuntimeError, match="query failed"):
            await resource.execute("INVALID SQL", None)

        assert events == ["rollback"]

        await resource.aclose()

        assert events == ["rollback", "connection_close"]


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

    def test_extract_failure_raises_action_execution_error_and_keeps_old_context_value(self):
        result = {
            "rows": [{"id": 1}],
            "row_count": 1,
            "columns": ["id"],
        }
        ctx = Context({"value": "old"})
        config = {"value": {"regex": r"(", "group": 1}}
        with pytest.raises(ActionExecutionError, match="Failed to extract variable"):
            extract_variables(result, config, ctx)
        assert ctx.get("value") == "old"

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
