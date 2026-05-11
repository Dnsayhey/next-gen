"""context.py unit tests"""

import pytest

from nextgen.core.context import Context


class TestContext:
    """Test Context variable system"""

    def test_initial_vars(self):
        ctx = Context({"key": "value"})
        assert ctx.get("key") == "value"
        assert ctx.get("nonexistent") is None

    def test_set_var(self):
        ctx = Context()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_render_string(self):
        ctx = Context({"name": "world"})
        result = ctx.render("hello ${name}")
        assert result == "hello world"

    def test_render_multiple_vars(self):
        ctx = Context({"host": "api.com", "port": "8080"})
        result = ctx.render("http://${host}:${port}/api")
        assert result == "http://api.com:8080/api"

    def test_render_nested_vars(self):
        ctx = Context({"host": "api.com", "base_url": "https://${host}"})
        result = ctx.render("${base_url}/api")
        assert result == "https://api.com/api"

    def test_render_pure_var_preserves_original_type(self):
        ctx = Context({"count": 3, "items": [1, 2], "payload": {"ok": True}})

        assert ctx.render("${count}") == 3
        assert ctx.render("${items}") == [1, 2]
        assert ctx.render("${payload}") == {"ok": True}

    def test_render_nested_pure_string_var(self):
        ctx = Context({"host": "api.com", "base_url": "https://${host}"})

        assert ctx.render("${base_url}") == "https://api.com"

    def test_render_vars_with_prefix_names(self):
        ctx = Context({"user": "alice", "user_name": "Alice Smith"})
        result = ctx.render("${user}:${user_name}")
        assert result == "alice:Alice Smith"

    def test_render_stops_on_cycles(self):
        ctx = Context({"a": "${b}", "b": "${a}"})
        result = ctx.render("${a}")
        assert result in {"${a}", "${b}"}

    def test_render_no_vars(self):
        ctx = Context()
        result = ctx.render("hello world")
        assert result == "hello world"

    def test_render_non_string(self):
        ctx = Context()
        assert ctx.render(123) == 123
        assert ctx.render(None) is None
        assert ctx.render([1, 2]) == [1, 2]

    def test_render_dict(self):
        ctx = Context({"host": "api.com"})
        data = {
            "url": "http://${host}/api",
            "headers": {"Authorization": "Bearer ${host}"},
        }
        result = ctx.render_dict(data)
        assert result["url"] == "http://api.com/api"
        assert result["headers"]["Authorization"] == "Bearer api.com"

    def test_render_dict_with_list(self):
        ctx = Context({"name": "test"})
        data = {"items": ["${name}1", "${name}2"]}
        result = ctx.render_dict(data)
        assert result["items"] == ["test1", "test2"]

    def test_render_dict_recurses_into_dicts_inside_lists(self):
        ctx = Context({"key": "Authorization", "token": "abc", "count": 3})
        data = {
            "params": [
                {"key": "${key}", "value": "Bearer ${token}"},
                {"key": "count", "value": "${count}"},
            ]
        }

        result = ctx.render_dict(data)

        assert result["params"] == [
            {"key": "Authorization", "value": "Bearer abc"},
            {"key": "count", "value": 3},
        ]

    def test_render_value_recurses_lists_and_dicts(self):
        ctx = Context({"name": "Alice"})

        assert ctx.render_value([{"name": "${name}"}]) == [{"name": "Alice"}]

    def test_override_var(self):
        ctx = Context({"key": "old"})
        ctx.set("key", "new")
        assert ctx.get("key") == "new"

    def test_snapshot_returns_deepcopy(self):
        ctx = Context({"nested": {"name": "Alice"}})
        snapshot = ctx.snapshot()

        snapshot["nested"]["name"] = "Bob"

        assert ctx.get("nested") == {"name": "Alice"}

    def test_derive_creates_isolated_child_with_shared_metadata(self):
        ctx = Context({"token": "root"}, metadata={"base_dir": "/case"})
        child = ctx.derive({"token": "child", "local": "value"})

        child.set("token", "updated")

        assert ctx.get("token") == "root"
        assert child.get("token") == "updated"
        assert child.get("local") == "value"
        assert child.metadata is ctx.metadata

    def test_derive_shares_runtime_resources(self):
        ctx = Context()
        resource = object()
        ctx.set_resource("resource", resource)

        child = ctx.derive()

        assert child.get_resource("resource") is resource
        child.set_resource("other", resource)
        assert ctx.get_resource("other") is resource

    @pytest.mark.asyncio
    async def test_close_resources_closes_async_resources(self):
        ctx = Context()

        class Resource:
            def __init__(self):
                self.closed = False

            async def aclose(self):
                self.closed = True

        resource = Resource()
        ctx.set_resource("resource", resource)

        await ctx.close_resources()

        assert resource.closed is True
        assert ctx.resources == {}

    def test_merge_sets_each_update(self):
        ctx = Context({"a": 1})

        ctx.merge({"b": 2, "a": 3})

        assert ctx.snapshot() == {"a": 3, "b": 2}
