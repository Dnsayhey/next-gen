"""scheduler.py 单元测试"""

import asyncio
import time

import pytest

from nextgen.core.model import StepNode, StepStatus, TestCase
from nextgen.core.scheduler import Scheduler, register_executor


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
        action_type="test_scheduler_action",
        action_config={"name": name},
        depends_on=depends_on or [],
        when=when,
        set_vars=set_vars or {},
        config=config or {},
    )


@pytest.fixture
def scheduler_executor_registry():
    """注册测试用 executor"""
    events: list[str] = []

    async def execute(action_config, ctx):
        name = action_config["name"]
        events.append(f"execute:{name}")

        if name == "sleepy":
            await asyncio.sleep(0.06)

        if name == "flaky":
            count = ctx.get("flaky_count") or 0
            ctx.set("flaky_count", count + 1)
            if count == 0:
                raise RuntimeError("boom")

        return {
            "status_code": 200,
            "body": {"name": name},
            "headers": {},
        }

    def extract(result, config, ctx):
        return {}

    def validate(result, assertions):
        return []

    register_executor("test_scheduler_action", execute, extract, validate)
    return events


class TestScheduler:
    """测试 Scheduler 运行时语义"""

    @pytest.mark.asyncio
    async def test_sequential_mode_uses_planned_dependencies(self, scheduler_executor_registry):
        testcase = TestCase(
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
    async def test_set_vars_is_visible_to_when(self, scheduler_executor_registry):
        testcase = TestCase(
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
        assert scheduler.context.get("env") == "staging"

    @pytest.mark.asyncio
    async def test_when_can_skip_step_after_set_vars(self, scheduler_executor_registry):
        testcase = TestCase(
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
        testcase = TestCase(
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
        testcase = TestCase(
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
            vars={"flaky_count": 0},
        )

        scheduler = Scheduler(testcase)
        result = await scheduler.run()

        assert result.steps[0].status == StepStatus.SUCCESS
        assert scheduler_executor_registry == ["execute:flaky", "execute:flaky"]
        assert scheduler.steps["flaky"].retry_count == 1
