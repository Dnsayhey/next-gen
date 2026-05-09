"""scheduler.py unit tests"""

import asyncio
import os
import time

import pytest

from nextgen.core.actions import ActionSpec, register_action, restore_actions, snapshot_actions
from nextgen.core.errors import ExecutionError, HookError, ValidationError
from nextgen.core.errors import ActionExecutionError
from nextgen.core.model import (
    ActionNode,
    AssertionNode,
    HookAction,
    StepNode,
    TestCase as CaseModel,
)
from nextgen.core.result import ActionResult, StepStatus
from nextgen.core.scheduler import Scheduler, StepRuntime
from nextgen.core.hooks import HOOK_REGISTRY, hook
from nextgen.parser.loader import parse_when


def make_step(
    name: str,
    *,
    depends_on: list[str] | None = None,
    when=None,
    set_vars: dict[str, str] | None = None,
    config: dict | None = None,
) -> StepNode:
    """Create a test StepNode"""
    return StepNode(
        name=name,
        action=ActionNode(type="test_scheduler_action", config={"name": name}),
        depends_on=depends_on or [],
        when=parse_when(when),
        set_vars=set_vars or {},
        config=config or {},
    )


@pytest.fixture
def scheduler_action_registry():
    """Register a test action"""
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

        return ActionResult(
            data={
                "status_code": 200,
                "body": {"name": name},
                "headers": {},
            },
            metric={"label": "status_code", "value": 200},
        )

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


@pytest.fixture(autouse=True)
def hook_registry_snapshot():
    hooks = HOOK_REGISTRY.copy()
    yield
    HOOK_REGISTRY.clear()
    HOOK_REGISTRY.update(hooks)


class TestScheduler:
    """Test Scheduler runtime semantics"""

    @pytest.mark.asyncio
    async def test_sequential_mode_runs_one_runnable_step_at_a_time(self, scheduler_action_registry):
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
        assert scheduler_action_registry == [
            "execute:a",
            "execute:b",
            "execute:c",
        ]

    @pytest.mark.asyncio
    async def test_fail_fast_defaults_to_true(self, scheduler_action_registry):
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
        assert scheduler_action_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_fail_fast_false_continues_independent_steps(self, scheduler_action_registry):
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
        assert scheduler_action_registry == ["execute:boom", "execute:after"]

    @pytest.mark.asyncio
    async def test_failed_dependency_is_skipped_even_when_fail_fast_disabled(self, scheduler_action_registry):
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
        assert scheduler_action_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_fail_fast_skips_parallel_steps_waiting_for_concurrency_slot(
        self,
        scheduler_action_registry,
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
        assert scheduler_action_registry == ["execute:boom"]

    @pytest.mark.asyncio
    async def test_set_vars_is_visible_to_when(self, scheduler_action_registry):
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
        assert scheduler_action_registry == ["execute:allowed"]
        assert scheduler.context.get("env") is None

    @pytest.mark.asyncio
    async def test_when_can_skip_step_after_set_vars(self, scheduler_action_registry):
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
        assert scheduler_action_registry == []

    @pytest.mark.asyncio
    async def test_step_timeout_covers_retry_and_wait(self, scheduler_action_registry):
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
        assert "timed out" in (result.steps[0].error or "")
        assert scheduler_action_registry == ["execute:flaky"]
        assert elapsed < 0.09

    @pytest.mark.asyncio
    async def test_retry_can_succeed_within_total_timeout(self, scheduler_action_registry):
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
        assert scheduler_action_registry == ["execute:flaky", "execute:flaky"]
        assert scheduler.steps["flaky"].retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_backoff_uses_exponential_delay(self, monkeypatch, scheduler_action_registry):
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
    async def test_parallel_mode_runs_independent_steps_concurrently(self, scheduler_action_registry):
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
    async def test_parallel_mode_schedules_dependents_as_soon_as_parent_finishes(self):
        actions = snapshot_actions()
        events: list[tuple[str, float]] = []

        async def execute(config, ctx):
            events.append((f"start:{config['name']}", time.perf_counter()))
            if config["name"] == "slow":
                await asyncio.sleep(0.08)
            if config["name"] == "fast":
                await asyncio.sleep(0.01)
            events.append((f"end:{config['name']}", time.perf_counter()))
            return ActionResult(data={}, metric={"label": "status_code", "value": 200})

        register_action(ActionSpec(
            name="dynamic_schedule_action",
            parse_config=lambda config: config,
            execute=execute,
            extract=lambda result, config, ctx: {},
            validate=lambda result, assertions: [],
            summarize=lambda config: config["name"],
        ))

        try:
            testcase = CaseModel(
                version=1,
                mode="parallel",
                steps={
                    "slow": StepNode(
                        name="slow",
                        action=ActionNode(type="dynamic_schedule_action", config={"name": "slow"}),
                    ),
                    "fast": StepNode(
                        name="fast",
                        action=ActionNode(type="dynamic_schedule_action", config={"name": "fast"}),
                    ),
                    "after_fast": StepNode(
                        name="after_fast",
                        action=ActionNode(type="dynamic_schedule_action", config={"name": "after_fast"}),
                        depends_on=["fast"],
                    ),
                },
            )

            scheduler = Scheduler(testcase, max_concurrency=2)
            result = await scheduler.run()
        finally:
            restore_actions(actions)

        times = dict(events)
        assert [step.status for step in result.steps] == [
            StepStatus.SUCCESS,
            StepStatus.SUCCESS,
            StepStatus.SUCCESS,
        ]
        assert times["start:after_fast"] < times["end:slow"]

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
            data = {
                "status_code": 500,
                "body": {"error": "boom"},
                "headers": {"x-request-id": "req-1"},
            }
            return ActionResult(
                data=data,
                action_input={"type": "snapshot_output"},
                action_output={
                    "status_code": 500,
                    "body": {"error": "boom"},
                    "headers": {"x-request-id": "req-1"},
                },
                metric={"label": "status_code", "value": 500},
            )

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
                        validate=[AssertionNode(op="eq", left="$$.status_code", right=200)],
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
    async def test_step_logic_uses_validation_error_for_assertion_failures(self):
        actions = snapshot_actions()

        async def execute(config, ctx):
            return ActionResult(data={}, action_input={}, action_output={})

        register_action(ActionSpec(
            name="validation_error_action",
            parse_config=lambda config: config,
            execute=execute,
            extract=lambda result, config, ctx: {},
            validate=lambda result, assertions: ["forced failure"],
            summarize=lambda config: "validation error action",
        ))

        try:
            step = StepRuntime(StepNode(
                name="failing",
                action=ActionNode(type="validation_error_action", config={}),
            ))
            scheduler = Scheduler(CaseModel(version=1, steps={"failing": step.node}))

            with pytest.raises(ValidationError, match="forced failure"):
                await scheduler._execute_step_logic(step, scheduler.context.derive())
        finally:
            restore_actions(actions)

    @pytest.mark.asyncio
    async def test_step_logic_uses_execution_error_for_missing_action(self):
        step = StepRuntime(StepNode(
            name="missing",
            action=ActionNode(type="missing_action", config={}),
        ))
        scheduler = Scheduler(CaseModel(version=1, steps={"missing": step.node}))

        with pytest.raises(ExecutionError, match="unregistered action"):
            await scheduler._execute_step_logic(step, scheduler.context.derive())

    @pytest.mark.asyncio
    async def test_execute_hooks_uses_hook_error_for_missing_hook(self):
        scheduler = Scheduler(CaseModel(version=1, steps={"one": make_step("one")}))

        with pytest.raises(HookError, match="unregistered hook"):
            await scheduler.execute_hooks([HookAction("missingHook", {})], scheduler.context, phase="test")

    @pytest.mark.asyncio
    async def test_testcase_and_step_hooks_run_in_expected_order(
        self,
        tmp_path,
        scheduler_action_registry,
    ):
        trace_file = tmp_path / "trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import hook",
                    "",
                    "@hook('trace')",
                    "def trace(file, value):",
                    "    with open(file, 'a', encoding='utf-8') as f:",
                    "        f.write(value + '\\n')",
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
        scheduler_action_registry,
    ):
        trace_file = tmp_path / "retry_trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import hook",
                    "",
                    "@hook('trace')",
                    "def trace(file, value):",
                    "    with open(file, 'a', encoding='utf-8') as f:",
                    "        f.write(value + '\\n')",
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
        scheduler_action_registry,
    ):
        trace_file = tmp_path / "after_trace.log"
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import hook",
                    "",
                    "@hook('traceVar')",
                    "def trace_var(ctx, file, source):",
                    "    value = ctx.get(source)",
                    "    with open(file, 'a', encoding='utf-8') as f:",
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
    async def test_before_all_failure_aborts_execution(self, tmp_path, scheduler_action_registry):
        hook_file = tmp_path / "hooks.py"
        hook_file.write_text(
            "\n".join(
                [
                    "from nextgen import hook",
                    "",
                    "@hook('boomHook')",
                    "def boom_hook():",
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

        assert scheduler_action_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "before_all" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_after_all_failure_marks_result_failed(self, scheduler_action_registry):
        @hook("boomAfterAllForResult")
        async def boom_after_all():
            raise RuntimeError("after all exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.hooks.after_all = [HookAction("boomAfterAllForResult", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_action_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "after_all" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_before_each_failure_marks_current_step_failed(
        self,
        scheduler_action_registry,
    ):
        @hook("boomBeforeEachForResult")
        async def boom_before_each():
            raise RuntimeError("before each exploded")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.hooks.before_each = [HookAction("boomBeforeEachForResult", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_action_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert result.summary["failed"] == 1
        assert "before_each" in (result.steps[0].error or "")

    @pytest.mark.asyncio
    async def test_after_each_runs_when_before_each_fails(
        self,
        tmp_path,
        scheduler_action_registry,
    ):
        trace_file = tmp_path / "before_each_failure.log"

        @hook("traceBeforeEachThenFail")
        def trace_before_each_then_fail(file):
            with open(file, "a", encoding="utf-8") as f:
                f.write("before_each\n")
            raise RuntimeError("before each exploded")

        @hook("traceAfterEachAfterBeforeFailure")
        def trace_after_each_after_before_failure(file):
            with open(file, "a", encoding="utf-8") as f:
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

        assert scheduler_action_registry == []
        assert result.steps[0].status == StepStatus.FAILED
        assert trace_file.read_text(encoding="utf-8").splitlines() == [
            "before_each",
            "after_each",
        ]

    @pytest.mark.asyncio
    async def test_after_hook_failure_does_not_block_extracted_variables(
        self,
        scheduler_action_registry,
    ):
        @hook("boomAfterForPublish")
        async def boom_after():
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

        assert scheduler_action_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[0].extracted == {"token": "one"}
        assert scheduler.context.get("token") == "one"

    @pytest.mark.asyncio
    async def test_after_hook_failure_does_not_block_later_after_hooks(
        self,
        tmp_path,
        scheduler_action_registry,
    ):
        trace_file = tmp_path / "after_best_effort.log"

        @hook("boomAfterBeforeTrace")
        async def boom_after_before_trace():
            raise RuntimeError("after exploded")

        @hook("traceAfterStillRuns")
        def trace_after_still_runs(file):
            with open(file, "a", encoding="utf-8") as f:
                f.write("after still ran\n")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].extract = {"token": "$.name"}
        testcase.steps["one"].hooks.after = [
            HookAction("boomAfterBeforeTrace", {}),
            HookAction("traceAfterStillRuns", {"file": str(trace_file)}),
        ]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_action_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.SUCCESS
        assert scheduler.context.get("token") == "one"
        assert trace_file.read_text(encoding="utf-8").splitlines() == ["after still ran"]

    @pytest.mark.asyncio
    async def test_export_can_use_extracted_values_and_publish_globals(
        self,
        scheduler_action_registry,
    ):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].extract = {"raw_token": "$.name"}
        testcase.steps["one"].export = {
            "auth_header": "Bearer ${raw_token}",
            "final_header": "${auth_header}",
        }

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert scheduler_action_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[0].extracted == {"raw_token": "one"}
        assert result.steps[0].exported == {
            "auth_header": "Bearer one",
            "final_header": "Bearer one",
        }
        assert scheduler.context.get("raw_token") == "one"
        assert scheduler.context.get("auth_header") == "Bearer one"
        assert scheduler.context.get("final_header") == "Bearer one"

    @pytest.mark.asyncio
    async def test_export_overrides_extract_when_names_conflict(
        self,
        scheduler_action_registry,
    ):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].extract = {"token": "$.name"}
        testcase.steps["one"].export = {"token": "Bearer ${token}"}

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].extracted == {"token": "one"}
        assert result.steps[0].exported == {"token": "Bearer one"}
        assert scheduler.context.get("token") == "Bearer one"

    @pytest.mark.asyncio
    async def test_export_does_not_see_after_hook_values(
        self,
        scheduler_action_registry,
    ):
        @hook("setAfterExportProbe")
        def set_after_export_probe(ctx):
            ctx.set("after_value", "late")

        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"one": make_step("one")},
        )
        testcase.steps["one"].export = {"exported_after_value": "${after_value}"}
        testcase.steps["one"].hooks.after = [HookAction("setAfterExportProbe", {})]

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.SUCCESS
        assert result.steps[0].exported == {"exported_after_value": "${after_value}"}
        assert scheduler.context.get("exported_after_value") == "${after_value}"
        assert scheduler.context.get("after_value") is None

    @pytest.mark.asyncio
    async def test_export_is_not_published_when_step_fails(
        self,
        scheduler_action_registry,
    ):
        testcase = CaseModel(
            version=1,
            mode="parallel",
            steps={"boom": make_step("boom")},
        )
        testcase.steps["boom"].export = {"should_not_publish": "value"}

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.FAILED
        assert result.steps[0].exported == {}
        assert scheduler.context.get("should_not_publish") is None

    @pytest.mark.asyncio
    async def test_after_each_failure_does_not_publish_extracted_variables(
        self,
        scheduler_action_registry,
    ):
        @hook("boomAfterEachForPublish")
        async def boom_after_each():
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

        assert scheduler_action_registry == ["execute:one"]
        assert result.steps[0].status == StepStatus.FAILED
        assert scheduler.context.get("token") is None

    @pytest.mark.asyncio
    async def test_retry_attempt_does_not_reuse_step_local_context(
        self,
        tmp_path,
        scheduler_action_registry,
    ):
        @hook("dirtyAttemptContext")
        def dirty_attempt_context(ctx, file):
            seen = ctx.get("attempt_local")
            with open(file, "a", encoding="utf-8") as f:
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
        assert scheduler_action_registry == ["execute:flaky", "execute:flaky"]
        assert lines == ["None", "None"]
