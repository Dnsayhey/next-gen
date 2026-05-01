"""context.py 单元测试"""

from nextgen.core.context import Context


class TestContext:
    """测试 Context 变量系统"""

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

    def test_override_var(self):
        ctx = Context({"key": "old"})
        ctx.set("key", "new")
        assert ctx.get("key") == "new"
