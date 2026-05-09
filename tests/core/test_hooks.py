"""hooks.py 单元测试"""

from pathlib import Path

import pytest

from nextgen.core.context import Context
from nextgen.core import hooks as hooks_module
from nextgen.core.hooks import (
    HOOK_REGISTRY,
    bind_hook_arguments,
    call_hook,
    discover_hooks,
    hook,
)


@pytest.fixture(autouse=True)
def hook_registry_snapshot():
    hooks = HOOK_REGISTRY.copy()
    yield
    HOOK_REGISTRY.clear()
    HOOK_REGISTRY.update(hooks)


class TestDiscoverHooks:
    """测试 hooks.py 自动发现"""

    def test_discover_hooks_from_outer_to_inner(self, tmp_path):
        root = tmp_path
        cases = root / "testcases"
        api = cases / "api"
        api.mkdir(parents=True)

        (root / "hooks.py").write_text("# root\n", encoding="utf-8")
        (cases / "hooks.py").write_text("# cases\n", encoding="utf-8")
        (api / "hooks.py").write_text("# api\n", encoding="utf-8")
        case_file = api / "login.yaml"
        case_file.write_text("version: 1\nsteps: {}\n", encoding="utf-8")

        found = discover_hooks(case_file, root)
        assert found == [
            root / "hooks.py",
            cases / "hooks.py",
            api / "hooks.py",
        ]

    def test_discover_hooks_returns_empty_when_case_is_outside_cwd(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        case_file = outside / "case.yaml"
        case_file.write_text("version: 1\nsteps: {}\n", encoding="utf-8")

        found = discover_hooks(case_file, tmp_path / "project")
        assert found == []

    def test_discover_hooks_returns_empty_when_no_hook_files_exist(self, tmp_path):
        cases = tmp_path / "testcases" / "api"
        cases.mkdir(parents=True)
        case_file = cases / "login.yaml"
        case_file.write_text("version: 1\nsteps: {}\n", encoding="utf-8")

        found = discover_hooks(case_file, tmp_path)

        assert found == []


class TestBuiltinHooks:
    """测试内置 hook 注册"""

    def test_builtin_hooks_are_registered(self):
        for name in ["sleep", "log", "get_timestamp", "get_time_str", "get_random_str", "set_vars"]:
            assert name in HOOK_REGISTRY

    @pytest.mark.asyncio
    async def test_log_rejects_unknown_level(self):
        with pytest.raises(ValueError, match="不支持的日志级别"):
            await call_hook(HOOK_REGISTRY["log"], Context(), {"level": "__dict__", "message": "hello"})

    @pytest.mark.asyncio
    async def test_var_hooks_require_var_param(self):
        with pytest.raises(ValueError, match="缺少参数: var"):
            await call_hook(HOOK_REGISTRY["get_timestamp"], Context(), {})

    @pytest.mark.asyncio
    async def test_get_time_str_sets_formatted_value(self):
        ctx = Context()

        await call_hook(HOOK_REGISTRY["get_time_str"], ctx, {"var": "today", "format": "%Y"})

        assert len(ctx.get("today")) == 4
        assert ctx.get("today").isdigit()

    @pytest.mark.asyncio
    async def test_set_vars_renders_and_sets_values_in_order(self):
        ctx = Context({"suffix": "abc"})

        await call_hook(
            HOOK_REGISTRY["set_vars"],
            ctx,
            {
                "dir": "new_${suffix}",
                "path": "/${dir}/file.txt",
                "items": ["${dir}", "${path}"],
            },
        )

        assert ctx.get("dir") == "new_abc"
        assert ctx.get("path") == "/new_abc/file.txt"
        assert ctx.get("items") == ["new_abc", "/new_abc/file.txt"]


class TestHookBinding:
    """测试 hook 函数签名绑定"""

    def test_duplicate_hook_name_is_rejected_by_default(self):
        @hook("duplicate_name")
        def first():
            return None

        with pytest.raises(ValueError, match="hook 已注册: duplicate_name"):
            @hook("duplicate_name")
            def second():
                return None

    def test_duplicate_hook_name_can_be_overridden_explicitly(self):
        @hook("override_name")
        def first():
            return None

        @hook("override_name", override=True)
        def second():
            return None

        assert HOOK_REGISTRY["override_name"].func is second

    def test_scalar_params_bind_to_single_required_arg(self):
        @hook("bind_scalar_required")
        def bind_scalar_required(seconds):
            return None

        kwargs = bind_hook_arguments(HOOK_REGISTRY["bind_scalar_required"], Context(), 2)

        assert kwargs == {"seconds": 2}

    def test_scalar_params_bind_to_single_optional_arg(self):
        @hook("bind_scalar_optional")
        def bind_scalar_optional(message=""):
            return None

        kwargs = bind_hook_arguments(HOOK_REGISTRY["bind_scalar_optional"], Context(), "hello")

        assert kwargs == {"message": "hello"}

    def test_scalar_params_bind_to_first_optional_arg(self):
        kwargs = bind_hook_arguments(HOOK_REGISTRY["log"], Context(), "hello")

        assert kwargs["message"] == "hello"
        assert "level" not in kwargs

    def test_scalar_params_reject_ambiguous_signature(self):
        @hook("bind_scalar_ambiguous")
        def bind_scalar_ambiguous(a, b):
            return None

        with pytest.raises(ValueError, match="不支持标量参数"):
            bind_hook_arguments(HOOK_REGISTRY["bind_scalar_ambiguous"], Context(), "raw")

    def test_unknown_dict_param_is_rejected(self):
        @hook("bind_unknown_param")
        def bind_unknown_param(message):
            return None

        with pytest.raises(ValueError, match="未知参数: extra"):
            bind_hook_arguments(
                HOOK_REGISTRY["bind_unknown_param"],
                Context(),
                {"message": "ok", "extra": "nope"},
            )

    def test_var_kwargs_accept_unknown_params(self):
        @hook("bind_kwargs")
        def bind_kwargs(ctx, **values):
            return None

        kwargs = bind_hook_arguments(HOOK_REGISTRY["bind_kwargs"], Context(), {"a": 1})

        assert set(kwargs) == {"ctx", "a"}
        assert kwargs["a"] == 1

    @pytest.mark.asyncio
    async def test_sync_hook_can_write_context(self):
        @hook("sync_context_write")
        def sync_context_write(ctx, value):
            ctx.set("value", value)

        ctx = Context()

        await call_hook(HOOK_REGISTRY["sync_context_write"], ctx, {"value": "ok"})

        assert ctx.get("value") == "ok"

    @pytest.mark.asyncio
    async def test_non_none_return_value_is_ignored_with_warning(self, monkeypatch):
        @hook("return_value_warning")
        def return_value_warning():
            return {"ignored": True}

        warnings = []
        monkeypatch.setattr(hooks_module.logger, "warning", warnings.append)

        await call_hook(HOOK_REGISTRY["return_value_warning"], Context(), {})

        assert len(warnings) == 1
        assert "returned a value and it was ignored" in warnings[0]
