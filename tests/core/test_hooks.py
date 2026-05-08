"""hooks.py 单元测试"""

from pathlib import Path

import pytest

from nextgen.core.context import Context
from nextgen.core.hooks import HOOK_REGISTRY, discover_hooks


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
        for name in ["sleep", "log", "getTimestamp", "getTimeStr", "getRandomStr"]:
            assert name in HOOK_REGISTRY

    @pytest.mark.asyncio
    async def test_log_rejects_unknown_level(self):
        with pytest.raises(ValueError, match="不支持的日志级别"):
            await HOOK_REGISTRY["log"](Context(), {"level": "__dict__", "message": "hello"})

    @pytest.mark.asyncio
    async def test_var_hooks_require_var_param(self):
        with pytest.raises(ValueError, match="必须包含 var"):
            await HOOK_REGISTRY["getTimestamp"](Context(), {})

    @pytest.mark.asyncio
    async def test_get_time_str_sets_formatted_value(self):
        ctx = Context()

        await HOOK_REGISTRY["getTimeStr"](ctx, {"var": "today", "format": "%Y"})

        assert len(ctx.get("today")) == 4
        assert ctx.get("today").isdigit()
