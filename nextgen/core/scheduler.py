"""调度器 - 状态机驱动的 DAG 调度"""

import asyncio
import time
from pathlib import Path
from typing import Any

from loguru import logger

from nextgen.core.actions import get_action
from nextgen.core.condition import evaluate_condition
from nextgen.core.context import Context
from nextgen.core.errors import ExecutionError, HookError, ValidationError
from nextgen.core.hooks import call_hook, get_hook, load_discovered_hooks
from nextgen.core.model import (
    AssertionNode,
    HookAction,
    StepNode,
    TestCase,
)
from nextgen.core.result import (
    ActionResult,
    StepResult,
    StepStatus,
    TestResult,
    TestStatus,
)
from nextgen.core.planner import build_graph


class StepRuntime:
    """步骤运行时状态"""

    def __init__(self, node: StepNode):
        self.node = node
        self.status = StepStatus.PENDING
        self.retry_count = 0
        self.error: str | None = None
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.result: ActionResult | None = None
        self.pending_extracts: dict[str, Any] = {}
        self.pending_exports: dict[str, Any] = {}

    @property
    def duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0

    @property
    def action_summary(self) -> str:
        """获取 action 摘要"""
        action = get_action(self.node.action.type)
        if action is None:
            return f"{self.node.action.type}: {self.node.name}"
        return action.summarize(self.node.action.config)


class Scheduler:
    """DAG 调度器"""

    def __init__(
        self,
        testcase: TestCase,
        max_concurrency: int = 10,
    ):
        self.testcase = testcase
        metadata = {"base_dir": testcase.base_dir} if testcase.base_dir else {}
        self.context = Context(testcase.vars, metadata=metadata)
        self.max_concurrency = max_concurrency
        self.graph = build_graph(testcase)
        self.loaded_hook_files: list[str] = []

        self.steps: dict[str, StepRuntime] = {
            name: StepRuntime(node)
            for name, node in testcase.steps.items()
        }

    async def execute_hooks(
        self,
        hooks: list[HookAction],
        ctx: Context,
        *,
        step: StepRuntime | None = None,
        phase: str,
    ) -> None:
        """顺序执行一组 hook"""
        for hook in hooks:
            handler = get_hook(hook.type)
            if handler is None:
                raise HookError(f"未注册的 hook: {hook.type}")

            params = ctx.render_value(hook.params)
            try:
                await call_hook(handler, ctx, params)
            except Exception as exc:
                target = step.node.name if step else "testcase"
                raise HookError(f"{phase} hook '{hook.type}' 执行失败 ({target}): {exc}") from exc

    async def execute_hooks_best_effort(
        self,
        hooks: list[HookAction],
        ctx: Context,
        *,
        step: StepRuntime,
        phase: str,
    ) -> None:
        """顺序执行 hook，HookError 只记录并继续后续 hook"""
        for hook in hooks:
            try:
                await self.execute_hooks([hook], ctx, step=step, phase=phase)
            except HookError as exc:
                logger.warning(str(exc))

    def is_runnable(self, step: StepRuntime) -> bool:
        """判断步骤是否可执行"""
        return (
            step.status == StepStatus.PENDING
            and all(
                self.steps[d].status == StepStatus.SUCCESS
                for d in self.graph[step.node.name]
            )
        )

    def should_skip(self, step: StepRuntime) -> bool:
        """判断步骤是否应跳过"""
        return any(
            self.steps[d].status in (StepStatus.FAILED, StepStatus.SKIPPED)
            for d in self.graph[step.node.name]
        )

    def has_failure(self) -> bool:
        """判断当前用例是否已有失败步骤"""
        return any(s.status == StepStatus.FAILED for s in self.steps.values())

    def _build_result(self, start_time: float, errors: list[str] | None = None) -> TestResult:
        """基于当前运行时状态构建测试结果"""
        total_ms = int((time.time() - start_time) * 1000)
        result_errors = errors or []
        results = []
        for name, runtime in self.steps.items():
            results.append(StepResult(
                name=name,
                status=runtime.status,
                duration_ms=runtime.duration_ms,
                action_summary=runtime.action_summary,
                metric=runtime.result.metric if runtime.result else None,
                action_input=runtime.result.action_input if runtime.result else None,
                action_output=runtime.result.action_output if runtime.result else None,
                error=runtime.error,
                extracted=runtime.pending_extracts,
                exported=runtime.pending_exports,
            ))

        status = (
            TestStatus.FAILED
            if result_errors or any(s.status == StepStatus.FAILED for s in results)
            else TestStatus.SUCCESS
        )

        return TestResult(
            testcase=Path(self.testcase.source_path).name if self.testcase.source_path else "",
            total_duration_ms=total_ms,
            steps=results,
            status=status,
            errors=result_errors,
        )

    def _mark_suite_failure(self, error: str) -> None:
        """将用例级失败映射到一个步骤结果，保证 summary/退出码可见"""
        for runtime in self.steps.values():
            if runtime.status in (StepStatus.PENDING, StepStatus.SUCCESS, StepStatus.SKIPPED):
                runtime.status = StepStatus.FAILED
                runtime.error = error
                return

    async def _execute_step_logic(self, step: StepRuntime, step_ctx: Context) -> None:
        """执行步骤的核心逻辑"""
        # 设置变量（在 action 之前）
        if step.node.set_vars:
            for key, value in step.node.set_vars.items():
                rendered = step_ctx.render(value)
                step_ctx.set(key, rendered)

        # 条件执行（可使用当前步骤的 set_vars）
        if not evaluate_condition(step.node.when, step_ctx):
            step.status = StepStatus.SKIPPED
            logger.info(f"条件不满足，跳过步骤: {step.node.name}")
            return

        await self.execute_hooks(
            step.node.hooks.before,
            step_ctx,
            step=step,
            phase="before",
        )

        action_type = step.node.action.type

        # 检查 action 是否存在
        action = get_action(action_type)
        if action is None:
            raise ExecutionError(f"未注册的 action 类型: {action_type}")

        # 执行
        result = await action.execute(
            step.node.action.config,
            step_ctx,
        )
        step.result = result

        # 验证
        assertions = [
            AssertionNode(
                op=assertion.op,
                left=assertion.left,
                right=step_ctx.render(assertion.right),
            )
            for assertion in step.node.validate
        ]
        errors = action.validate(result.data, assertions)
        if errors:
            raise ValidationError("; ".join(errors))

        # 提取变量
        if step.node.extract:
            action.extract(result.data, step.node.extract, step_ctx)
            step.pending_extracts = {key: step_ctx.get(key) for key in step.node.extract}
        else:
            step.pending_extracts = {}

        if step.node.export:
            step.pending_exports = {}
            for key, value in step.node.export.items():
                rendered = step_ctx.render_value(value)
                step_ctx.set(key, rendered)
                step.pending_exports[key] = rendered
        else:
            step.pending_exports = {}

        step.status = StepStatus.SUCCESS

        await self.execute_hooks_best_effort(
            step.node.hooks.after,
            step_ctx,
            step=step,
            phase="after",
        )

    async def _run_step_with_retry(self, step: StepRuntime) -> None:
        """执行单个步骤，重试和跳过都在一个生命周期内完成"""
        max_retry = step.node.config.get("retry", 0)
        base_step_ctx = self.context.derive()

        try:
            await self.execute_hooks(
                self.testcase.hooks.before_each,
                base_step_ctx,
                step=step,
                phase="before_each",
            )
        except Exception as exc:
            step.error = str(exc)
            step.status = StepStatus.FAILED
            logger.error(str(exc))
            before_each_failed = True
        else:
            before_each_failed = False

        step_ctx = base_step_ctx
        try:
            if not before_each_failed:
                while True:
                    step.status = StepStatus.RUNNING
                    step.pending_extracts = {}
                    step.pending_exports = {}
                    step_ctx = base_step_ctx.derive()

                    try:
                        await self._execute_step_logic(step, step_ctx)
                        return

                    except Exception as e:
                        action_input = getattr(e, "action_input", None)
                        if action_input is not None:
                            if step.result is None:
                                step.result = ActionResult(data={}, action_input=action_input)
                            elif step.result.action_input is None:
                                step.result.action_input = action_input
                        step.error = str(e)

                        if step.retry_count < max_retry:
                            step.retry_count += 1
                            step.status = StepStatus.RETRYING

                            # 计算重试延迟
                            if step.node.config.get("retry_backoff"):
                                base_delay = step.node.config.get("retry_delay", 1)
                                max_delay = step.node.config.get("retry_max_delay", 60)
                                delay = min(base_delay * (2 ** (step.retry_count - 1)), max_delay)
                            else:
                                delay = step.node.config.get("retry_delay", 1)

                            logger.warning(
                                f"步骤 {step.node.name} 失败，"
                                f"重试 {step.retry_count}/{max_retry}，"
                                f"等待 {delay}秒"
                            )
                            await asyncio.sleep(delay)
                            continue

                        step.status = StepStatus.FAILED
                        logger.error(f"步骤 {step.node.name} 失败: {e}")
                        return
        finally:
            if step.status != StepStatus.PENDING:
                try:
                    await self.execute_hooks(
                        self.testcase.hooks.after_each,
                        step_ctx,
                        step=step,
                        phase="after_each",
                    )
                except Exception as exc:
                    step.error = str(exc)
                    step.status = StepStatus.FAILED
                    logger.error(str(exc))

            if step.status == StepStatus.SUCCESS:
                self.context.merge({**step.pending_extracts, **step.pending_exports})

            if step.status != StepStatus.SUCCESS:
                step.pending_extracts = {}
                step.pending_exports = {}

    async def run_step(self, step: StepRuntime) -> None:
        """执行单个步骤（步骤级超时覆盖全部重试）"""
        step.start_time = time.time()

        try:
            if self.testcase.fail_fast and self.has_failure():
                step.status = StepStatus.SKIPPED
                logger.info(f"fail_fast 生效，跳过步骤: {step.node.name}")
                return

            step_timeout = step.node.config.get("timeout")

            if step_timeout:
                await asyncio.wait_for(
                    self._run_step_with_retry(step),
                    timeout=step_timeout,
                )
            else:
                await self._run_step_with_retry(step)

        except asyncio.TimeoutError:
            step.error = f"步骤执行超时（{step.node.config.get('timeout')}秒）"
            step.status = StepStatus.FAILED
            logger.error(f"步骤 {step.node.name} 超时")

        finally:
            step.end_time = time.time()

    async def run(self) -> TestResult:
        """执行测试用例"""
        logger.info(f"开始执行测试用例，共 {len(self.steps)} 个步骤")
        start_time = time.time()

        if self.testcase.source_path:
            hook_root = self.testcase.base_dir or "."
            self.loaded_hook_files = [
                str(path) for path in load_discovered_hooks(
                    self.testcase.source_path,
                    hook_root,
                )
            ]

        try:
            await self.execute_hooks(
                self.testcase.hooks.before_all,
                self.context,
                phase="before_all",
            )
        except Exception as exc:
            error = str(exc)
            logger.error(error)
            self._mark_suite_failure(error)
            return self._build_result(start_time, [error])

        active_tasks: dict[asyncio.Task[None], StepRuntime] = {}

        def start_step(step: StepRuntime) -> None:
            step.status = StepStatus.RUNNING
            active_tasks[asyncio.create_task(self.run_step(step))] = step

        while True:
            if self.testcase.fail_fast and self.has_failure():
                for s in self.steps.values():
                    if s.status == StepStatus.PENDING:
                        s.status = StepStatus.SKIPPED
                        logger.info(f"fail_fast 生效，跳过步骤: {s.node.name}")
                if not active_tasks:
                    break

            pending = [
                s for s in self.steps.values()
                if s.status == StepStatus.PENDING
            ]

            if not pending and not active_tasks:
                break

            # 标记应跳过的步骤
            for s in pending:
                if self.should_skip(s):
                    s.status = StepStatus.SKIPPED
                    logger.info(f"跳过步骤: {s.node.name}")

            # 找出可执行的步骤
            runnable = [s for s in pending if self.is_runnable(s)]
            if self.testcase.mode == "sequential" and runnable:
                runnable = [runnable[0]]

            capacity = self.max_concurrency - len(active_tasks)
            for step in runnable[:capacity]:
                start_step(step)

            if active_tasks:
                done, _ = await asyncio.wait(
                    active_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    active_tasks.pop(task)
                    task.result()
                continue

            if not any(s.status == StepStatus.PENDING for s in self.steps.values()):
                break
            break

        after_all_errors: list[str] = []
        try:
            await self.execute_hooks(
                self.testcase.hooks.after_all,
                self.context,
                phase="after_all",
            )
        except Exception as exc:
            after_all_errors.append(str(exc))
            logger.error(after_all_errors[-1])
            self._mark_suite_failure(after_all_errors[-1])

        return self._build_result(start_time, after_all_errors)
