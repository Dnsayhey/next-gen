"""scheduler.py 单元测试"""

import asyncio
import os
import time

import pytest

from nextgen.core.actions import ActionSpec, register_action, restore_actions, snapshot_actions
from nextgen.core.errors import ActionExecutionError
from nextgen.core.model import (
    ActionNode,
    AssertionNode,
    HookAction,
    StepNode,
    StepStatus,
    TestCase as CaseModel,
)
from nextgen.core.scheduler import Scheduler
from nextgen.core.hooks import register_hook


def make_step(
    name: str,
    *,
    depends_on: list[str] | None = None,
    when=None,
    set_vars: dict[str, str] | None = None,
    config: dict | None = None,
) -> StepNode:
    """创建测试用 StepNode"""
    return StepNode(
        name=name,
        action=ActionNode(type="test_scheduler_action", config={"name": name}),
        depends_on=depends_on or [],
        when=when,
        set_vars=set_vars or {},
        config=config or {},
    )


@pytest.fixture
def scheduler_executor_registry():
    """注册测试用 action"""
    actions = snapshot_actions()
    events: list[str] = []

    async def execute(config, ctx):
        name = config["name"]
        events.append(f"execute:{name}")

        if name == "boom":
            raise RuntimeError("boom")

        if name == "sleepy":
            await asyncio.sleep(0.06)

        if name == "flaky":
            if events.count("execute:flaky") == 1:
                raise RuntimeError("boom")

        return {
            "status_code": 200,
            "body": {"name": name},
            "headers": {},
        }

    def extract(result, config, ctx):
        extracted = {}
        body = result.get("body", {})
        for var_name, path in config.items():
            if path == "$.name":
                value = body.get("name")
            else:
                value = None
            ctx.set(var_name, value)
            extracted[var_name] = value
        return extracted

    def validate(result, assertions):
        return []

    register_action(ActionSpec(
        name="test_scheduler_action",
        parse_config=lambda config: config,
        execute=execute,
        extract=extract,
        validate=validate,
        summarize=lambda config: f"test: {config['name']}",
    ))
    yield events
    restore_actions(actions)


class TestScheduler:
    """测试 Scheduler 运行时语义"""

    @pytest.mark.asyncio
    async def test_sequential_mode_runs_one_runnable_step_at_a_time(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="sequential",
            steps={
                "a": make_step("a"),
                "b": make_step("b"),
                "c": make_step("c"),
            },
        )

        scheduler = Scheduler(testcase, max_concurrency=3)
        result = await scheduler.run()

        assert [step.status for step in result.steps] == [
            StepStatus.SUCCESS,
            StepStatus.SUCCESS,
            StepStatus.SUCCESS,
        ]
        assert scheduler_executor_registry == [
            "execute:a",
            "execute:b",
            "execute:c",
        ]

    @pytest.mark.asyncio
    async def test_fail_fast_defaults_to_true(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="sequential",
            steps={
                "boom": make_step("boom"),
                "after": make_step("after"),
            },
        )

        scheduler = Scheduler(testcase, max_concurrency=3)
        result = await scheduler.run()

        assert [step.status for step in result.steps] == [
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        ]
        assert scheduler_executor_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_fail_fast_false_continues_independent_steps(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="sequential",
            fail_fast=False,
            steps={
                "boom": make_step("boom"),
                "after": make_step("after"),
            },
        )

        scheduler = Scheduler(testcase, max_concurrency=3)
        result = await scheduler.run()

        assert [step.status for step in result.steps] == [
            StepStatus.FAILED,
            StepStatus.SUCCESS,
        ]
        assert scheduler_executor_registry == ["execute:boom", "execute:after"]

    @pytest.mark.asyncio
    async def test_failed_dependency_is_skipped_even_when_fail_fast_disabled(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            fail_fast=False,
            steps={
                "boom": make_step("boom"),
                "after": make_step("after", depends_on=["boom"]),
            },
        )

        scheduler = Scheduler(testcase, max_concurrency=3)
        result = await scheduler.run()

        assert [step.status for step in result.steps] == [
            StepStatus.FAILED,
            StepStatus.SKIPPED,
        ]
        assert scheduler_executor_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_fail_fast_skips_parallel_steps_waiting_for_concurrency_slot(
        self,
        scheduler_executor_registry,
    ):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            fail_fast=True,
            steps={
                "boom": make_step("boom"),
                "after_a": make_step("after_a"),
                "after_b": make_step("after_b"),
            },
        )

        scheduler = Scheduler(testcase, max_concurrency=1)
        result = await scheduler.run()

        assert [step.status for step in result.steps] == [
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.SKIPPED,
        ]
        assert scheduler_executor_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_set_vars_is_visible_to_when(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "allowed": make_step(
                    "allowed",
                    set_vars={"env": "staging"},
                    when=[{"eq": ["${env}", "staging"]}],
                ),
            },
        )

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.SUCCESS
        assert scheduler_executor_registry == ["execute:allowed"]
        assert scheduler.context.get("env") is None

    @pytest.mark.asyncio
    async def test_when_can_skip_step_after_set_vars(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "blocked": make_step(
                    "blocked",
                    set_vars={"env": "prod"},
                    when=[{"eq": ["${env}", "staging"]}],
                ),
            },
        )

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.SKIPPED
        assert scheduler_executor_registry == []

    @pytest.mark.asyncio
    async def test_step_timeout_covers_retry_and_wait(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "flaky": make_step(
                    "flaky",
                    config={
                        "retry": 1,
                        "retry_delay": 0.05,
                        "timeout": 0.04,
                    },
                ),
            },
        )

        scheduler = Scheduler(testcase)
        start = time.time()
        result = await scheduler.run()
        elapsed = time.time() - start

        assert result.steps[0].status == StepStatus.FAILED
        assert "超时" in (result.steps[0].error or "")
        assert scheduler_executor_registry == ["execute:flaky"]
        assert elapsed < 0.09

    @pytest.mark.asyncio
    async def test_retry_can_succeed_within_total_timeout(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "flaky": make_step(
                    "flaky",
                    config={
                        "retry": 1,
                        "retry_delay": 0.01,
                        "timeout": 0.2,
                    },
                ),
            },
        )

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.SUCCESS
        assert scheduler_executor_registry == ["execute:flaky", "execute:flaky"]
        assert scheduler.steps["flaky"].retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_backoff_uses_exponential_delay(self, monkeypatch, scheduler_executor_registry):
        delays = []

        async def fake_sleep(delay):
            delays.append(delay)

        monkeypatch.setattr("nextgen.core.scheduler.asyncio.sleep", fake_sleep)

        testcase = CaseModel(
            version=1,
            mode="parallel",
            fail_fast=False,
            steps={
                "boom": make_step(
                    "boom",
                    config={
                        "retry": 3,
                        "retry_delay": 2,
                        "retry_backoff": True,
                        "retry_max_delay": 5,
                    },
                ),
            },
        )

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.FAILED
        assert delays == [2, 4, 5]

    @pytest.mark.asyncio
    async def test_parallel_mode_runs_independent_steps_concurrently(self, scheduler_executor_registry):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "sleepy_a": make_step("sleepy_a"),
                "sleepy_b": make_step("sleepy_b"),
            },
        )
        testcase.steps["sleepy_a"].action.config["name"] = "sleepy"
        testcase.steps["sleepy_b"].action.config["name"] = "sleepy"

        scheduler = Scheduler(testcase, max_concurrency=2)
        start = time.perf_counter()
        result = await scheduler.run()
        elapsed = time.perf_counter() - start

        assert [step.status for step in result.steps] == [
            StepStatus.SUCCESS,
            StepStatus.SUCCESS,
        ]
        assert elapsed < 0.11

    @pytest.mark.asyncio
    async def test_failed_action_can_attach_request_snapshot(self):
        actions = snapshot_actions()

        async def execute(config, ctx):
            raise ActionExecutionError(
                "connection failed",
                {
                    "type": "http",
                    "method": "GET",
                    "url": "https://example.com/api",
                    "headers": {"Authorization": "Bearer token"},
                    "params": {"q": "test"},
                    "body_type": None,
                    "body": None,
                    "timeout": None,
                },
            )

        register_action(ActionSpec(
            name="snapshot_failure",
            parse_config=lambda config: config,
            execute=execute,
            extract=lambda result, config, ctx: {},
            validate=lambda result, assertions: [],
            summarize=lambda config: "GET https://example.com/api",
        ))

        try:
            testcase = CaseModel(
                version=1,
                mode="parallel",
                steps={
                    "failing": StepNode(
                        name="failing",
                        action=ActionNode(type="snapshot_failure", config={}),
                    ),
                },
            )

            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            restore_actions(actions)

        assert result.steps[0].status == StepStatus.FAILED
        assert result.steps[0].action_input == {
            "type": "http",
            "method": "GET",
            "url": "https://example.com/api",
            "headers": {"Authorization": "Bearer token"},
            "params": {"q": "test"},
            "body_type": None,
            "body": None,
            "timeout": None,
        }
        assert result.steps[0].action_output is None

    @pytest.mark.asyncio
    async def test_validation_failure_preserves_action_output(self):
        actions = snapshot_actions()

        async def execute(config, ctx):
            return {
                "status_code": 500,
                "body": {"error": "boom"},
                "headers": {"x-request-id": "req-1"},
                "action_input": {"type": "snapshot_output"},
                "action_output": {
                    "status_code": 500,
                    "body": {"error": "boom"},
                    "headers": {"x-request-id": "req-1"},
                },
            }

        register_action(ActionSpec(
            name="snapshot_output",
            parse_config=lambda config: config,
            execute=execute,
            extract=lambda result, config, ctx: {},
            validate=lambda result, assertions: ["forced failure"],
            summarize=lambda config: "snapshot output",
        ))

        try:
            testcase = CaseModel(
                version=1,
                mode="parallel",
                steps={
                    "failing": StepNode(
                        name="failing",
                        action=ActionNode(type="snapshot_output", config={}),
                        validate=[AssertionNode(op="eq", left="$.status_code", right=200)],
                    ),
                },
            )

            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            restore_actions(actions)

        assert result.steps[0].status == StepStatus.FAILED
        assert result.steps[0].action_input == {"type": "snapshot_output"}
        assert result.steps[0].action_output == {
            "status_code": 500,
            "body": {"error": "boom"},
            "headers": {"x-request-id": "req-1"},
        }

    @pytest.mark.asyncio
    async def test_testcase_and_step_hooks_run_in_expected_order(
        self,
        tmp_path,
        scheduler_executor_registry,
    ):
        trace_file = tmp_path / "trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import register_hook",
                    "",
                    "@register_hook('trace')",
                    "async def trace(ctx, params):",
                    "    with open(params['file'], 'a', encoding='utf-8') as f:",
                    "        f.write(params['value'] + '\\n')",
                ]
            )
        )

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "one": make_step(
                    "one",
                    set_vars={"from_step": "value"},
                ),
            },
            source_path=str(tmp_path / "case.yaml"),
        )
        testcase.hooks.before_all = [
            HookAction("trace", {"file": str(trace_file), "value": "before_all"})
        ]
        testcase.hooks.before_each = [
            HookAction("trace", {"file": str(trace_file), "value": "before_each"}),
        ]
        testcase.hooks.after_each = [
            HookAction("trace", {"file": str(trace_file), "value": "after_each"})
        ]
        testcase.hooks.after_all = [
            HookAction("trace", {"file": str(trace_file), "value": "after_all"})
        ]
        testcase.steps["one"].hooks.before = [
            HookAction("trace", {"file": str(trace_file), "value": "before"})
        ]
        testcase.steps["one"].hooks.after = [
            HookAction("trace", {"file": str(trace_file), "value": "after"})
        ]

        previous_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            os.chdir(previous_cwd)

        assert result.steps[0].status == StepStatus.SUCCESS
        assert trace_file.read_text(encoding="utf-8").splitlines() == [
            "before_all",
            "before_each",
            "before",
            "after",
            "after_each",
            "after_all",
        ]
        assert scheduler.loaded_hook_files == [str(hook_file)]

    @pytest.mark.asyncio
    async def test_before_each_and_after_each_run_once_across_retry(
        self,
        tmp_path,
        scheduler_executor_registry,
    ):
        trace_file = tmp_path / "retry_trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import register_hook",
                    "",
                    "@register_hook('trace')",
                    "async def trace(ctx, params):",
                    "    with open(params['file'], 'a', encoding='utf-8') as f:",
                    "        f.write(params['value'] + '\\n')",
                ]
            )
        )

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "flaky": make_step(
                    "flaky",
                    config={"retry": 1, "retry_delay": 0.01, "timeout": 0.2},
                ),
            },
            source_path=str(tmp_path / "case.yaml"),
        )
        testcase.hooks.before_each = [
            HookAction("trace", {"file": str(trace_file), "value": "before_each"})
        ]
        testcase.hooks.after_each = [
            HookAction("trace", {"file": str(trace_file), "value": "after_each"})
        ]
        testcase.steps["flaky"].hooks.before = [
            HookAction("trace", {"file": str(trace_file), "value": "before"})
        ]
        testcase.steps["flaky"].hooks.after = [
            HookAction("trace", {"file": str(trace_file), "value": "after"})
        ]

        previous_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            os.chdir(previous_cwd)

        assert result.steps[0].status == StepStatus.SUCCESS
        assert trace_file.read_text(encoding="utf-8").splitlines() == [
            "before_each",
            "before",
            "before",
            "after",
            "after_each",
        ]

    @pytest.mark.asyncio
    async def test_after_hook_can_see_extracted_variables(
        self,
        tmp_path,
        scheduler_executor_registry,
    ):
        trace_file = tmp_path / "after_trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import register_hook",
                    "",
                    "@register_hook('traceVar')",
                    "async def trace_var(ctx, params):",
                    "    value = ctx.get(params['source'])",
                    "    with open(params['file'], 'a', encoding='utf-8') as f:",
                    "        f.write(str(value) + '\\n')",
                ]
            )
        )

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "one": make_step("one"),
            },
            source_path=str(tmp_path / "case.yaml"),
        )
        testcase.steps["one"].extract = {"token": "$.name"}
        testcase.steps["one"].hooks.after = [
            HookAction("traceVar", {"file": str(trace_file), "source": "token"})
        ]

        previous_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            os.chdir(previous_cwd)

        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[0].extracted == {"token": "one"}
        assert scheduler.context.get("token") == "one"
        assert trace_file.read_text(encoding="utf-8").splitlines() == ["one"]

    @pytest.mark.asyncio
    async def test_before_all_failure_aborts_execution(self, tmp_path, scheduler_executor_registry):
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import register_hook",
                    "",
                    "@register_hook('boomHook')",
                    "async def boom_hook(ctx, params):",
                    "    raise RuntimeError('boom')",
                ]
            )
        )

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
            source_path=str(tmp_path / "case.yaml"),
        )
        testcase.hooks.before_all = [
            __import__("nextgen.core.model", fromlist=["HookAction"]).HookAction("boomHook", {})
        ]

        previous_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            scheduler = Scheduler(testcase)
            result = await scheduler.run()
        finally:
            os.chdir(previous_cwd)

        assert scheduler_executor_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "before_all" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_after_all_failure_marks_result_failed(self, scheduler_executor_registry):
        @register_hook("boomAfterAllForResult")
        async def boom_after_all(ctx, params):
            raise RuntimeError("after all exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.hooks.after_all = [HookAction("boomAfterAllForResult", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_executor_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "after_all" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_before_each_failure_marks_current_step_failed(
        self,
        scheduler_executor_registry,
    ):
        @register_hook("boomBeforeEachForResult")
        async def boom_before_each(ctx, params):
            raise RuntimeError("before each exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.hooks.before_each = [HookAction("boomBeforeEachForResult", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_executor_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "before_each" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_after_each_runs_when_before_each_fails(
        self,
        tmp_path,
        scheduler_executor_registry,
    ):
        trace_file = tmp_path / "before_each_failure.log"

        @register_hook("traceBeforeEachThenFail")
        async def trace_before_each_then_fail(ctx, params):
            with open(params["file"], "a", encoding="utf-8") as f:
                f.write("before_each\n")
            raise RuntimeError("before each exploded")

        @register_hook("traceAfterEachAfterBeforeFailure")
        async def trace_after_each_after_before_failure(ctx, params):
            with open(params["file"], "a", encoding="utf-8") as f:
                f.write("after_each\n")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.hooks.before_each = [
            HookAction("traceBeforeEachThenFail", {"file": str(trace_file)})
        ]
        testcase.hooks.after_each = [
            HookAction("traceAfterEachAfterBeforeFailure", {"file": str(trace_file)})
        ]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_executor_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert trace_file.read_text(encoding="utf-8").splitlines() == [
            "before_each",
            "after_each",
        ]

    @pytest.mark.asyncio
    async def test_after_hook_failure_does_not_publish_extracted_variables(
        self,
        scheduler_executor_registry,
    ):
        @register_hook("boomAfterForPublish")
        async def boom_after(ctx, params):
            raise RuntimeError("after exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].extract = {"token": "$.name"}
        testcase.steps["one"].hooks.after = [HookAction("boomAfterForPublish", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_executor_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.FAILED
        assert scheduler.context.get("token") is None

    @pytest.mark.asyncio
    async def test_after_each_failure_does_not_publish_extracted_variables(
        self,
        scheduler_executor_registry,
    ):
        @register_hook("boomAfterEachForPublish")
        async def boom_after_each(ctx, params):
            raise RuntimeError("after each exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].extract = {"token": "$.name"}
        testcase.hooks.after_each = [HookAction("boomAfterEachForPublish", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_executor_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.FAILED
        assert scheduler.context.get("token") is None

    @pytest.mark.asyncio
    async def test_retry_attempt_does_not_reuse_step_local_context(
        self,
        tmp_path,
        scheduler_executor_registry,
    ):
        @register_hook("dirtyAttemptContext")
        async def dirty_attempt_context(ctx, params):
            seen = ctx.get("attempt_local")
            with open(params["file"], "a", encoding="utf-8") as f:
                f.write(str(seen) + "\n")
            ctx.set("attempt_local", "dirty")

        trace_file = tmp_path / "attempt_context_trace.log"

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={
                "flaky": make_step(
                    "flaky",
                    config={"retry": 1, "retry_delay": 0.01, "timeout": 0.2},
                ),
            },
        )
        testcase.steps["flaky"].hooks.before = [
            HookAction("dirtyAttemptContext", {"file": str(trace_file)})
        ]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()
        lines = trace_file.read_text(encoding="utf-8").splitlines()

        assert result.steps[0].status == StepStatus.SUCCESS
        assert scheduler_executor_registry == ["execute:flaky", "execute:flaky"]
        assert lines == ["None", "None"]
