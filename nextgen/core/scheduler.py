"""调度器 - 状态机驱动的 DAG 调度"""

import asyncio
import time
from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.model import (
    StepNode,
    StepResult,
    StepStatus,
    TestCase,
    TestResult,
)
from nextgen.executors.http import execute_request, extract_variables, validate_response


# Executor 注册表
EXECUTOR_REGISTRY = {
    "request": {
        "execute": execute_request,
        "extract": extract_variables,
        "validate": validate_response,
    },
}


def register_executor(
    action_type: str,
    execute_fn,
    extract_fn,
    validate_fn,
) -> None:
    """注册新的 executor"""
    EXECUTOR_REGISTRY[action_type] = {
        "execute": execute_fn,
        "extract": extract_fn,
        "validate": validate_fn,
    }


class StepRuntime:
    """步骤运行时状态"""

    def __init__(self, node: StepNode):
        self.node = node
        self.status = StepStatus.PENDING
        self.retry_count = 0
        self.error: str | None = None
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.result: dict[str, Any] | None = None

    @property
    def duration_ms(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0

    @property
    def request_summary(self) -> str:
        """获取请求摘要"""
        if self.node.action_type == "request":
            config = self.node.action_config
            method = config.get("method", "").upper()
            url = config.get("url", "")
            return f"{method} {url}"
        return f"{self.node.action_type}: {self.node.name}"


class Scheduler:
    """DAG 调度器"""

    def __init__(
        self,
        testcase: TestCase,
        max_concurrency: int = 10,
    ):
        self.testcase = testcase
        self.context = Context(testcase.vars)
        self.semaphore = asyncio.Semaphore(max_concurrency)

        self.steps: dict[str, StepRuntime] = {
            name: StepRuntime(node)
            for name, node in testcase.steps.items()
        }

    def is_runnable(self, step: StepRuntime) -> bool:
        """判断步骤是否可执行"""
        return (
            step.status == StepStatus.PENDING
            and all(
                self.steps[d].status == StepStatus.SUCCESS
                for d in step.node.depends_on
            )
        )

    def should_skip(self, step: StepRuntime) -> bool:
        """判断步骤是否应跳过"""
        return any(
            self.steps[d].status in (StepStatus.FAILED, StepStatus.SKIPPED)
            for d in step.node.depends_on
        )

    async def _execute_step_logic(self, step: StepRuntime) -> None:
        """执行步骤的核心逻辑"""
        action_type = step.node.action_type

        # 检查 executor 是否存在
        if action_type not in EXECUTOR_REGISTRY:
            raise ValueError(f"未注册的 action 类型: {action_type}")

        executor = EXECUTOR_REGISTRY[action_type]

        # 执行
        result = await executor["execute"](
            step.node.action_config,
            self.context,
        )
        step.result = result

        # 验证
        errors = executor["validate"](result, step.node.validate)
        if errors:
            raise AssertionError("; ".join(errors))

        # 提取变量
        if step.node.extract:
            executor["extract"](result, step.node.extract, self.context)

        step.status = StepStatus.SUCCESS

    async def run_step(self, step: StepRuntime) -> None:
        """执行单个步骤（支持超时）"""
        async with self.semaphore:
            step.status = StepStatus.RUNNING
            step.start_time = time.time()

            try:
                # 获取步骤级超时配置
                step_timeout = step.node.config.get("timeout")

                if step_timeout:
                    # 使用 asyncio.wait_for 实现超时
                    await asyncio.wait_for(
                        self._execute_step_logic(step),
                        timeout=step_timeout,
                    )
                else:
                    await self._execute_step_logic(step)

            except asyncio.TimeoutError:
                step.error = f"步骤执行超时（{step.node.config.get('timeout')}秒）"
                step.status = StepStatus.FAILED
                logger.error(f"步骤 {step.node.name} 超时")

            except Exception as e:
                step.error = str(e)

                # 重试逻辑
                max_retry = step.node.config.get("retry", 0)
                if step.retry_count < max_retry:
                    step.retry_count += 1
                    step.status = StepStatus.RETRYING
                    logger.warning(
                        f"步骤 {step.node.name} 失败，"
                        f"重试 {step.retry_count}/{max_retry}"
                    )
                    await asyncio.sleep(1)  # 固定间隔
                    return await self.run_step(step)

                step.status = StepStatus.FAILED
                logger.error(f"步骤 {step.node.name} 失败: {e}")

            finally:
                step.end_time = time.time()

    async def run(self) -> TestResult:
        """执行测试用例"""
        logger.info(f"开始执行测试用例，共 {len(self.steps)} 个步骤")
        start_time = time.time()

        while True:
            pending = [
                s for s in self.steps.values()
                if s.status == StepStatus.PENDING
            ]

            if not pending:
                break

            # 标记应跳过的步骤
            for s in pending:
                if self.should_skip(s):
                    s.status = StepStatus.SKIPPED
                    logger.info(f"跳过步骤: {s.node.name}")

            # 找出可执行的步骤
            runnable = [s for s in pending if self.is_runnable(s)]

            if not runnable:
                # 检查是否还有正在运行或重试的步骤
                active = [
                    s for s in self.steps.values()
                    if s.status in (StepStatus.RUNNING, StepStatus.RETRYING)
                ]
                if not active:
                    break
                await asyncio.sleep(0.1)
                continue

            # 并发执行
            await asyncio.gather(
                *[self.run_step(s) for s in runnable]
            )

        # 构建结果
        total_ms = int((time.time() - start_time) * 1000)
        results = []
        for name, runtime in self.steps.items():
            results.append(StepResult(
                name=name,
                status=runtime.status,
                duration_ms=runtime.duration_ms,
                request_summary=runtime.request_summary,
                response_status=runtime.result.get("status_code") if runtime.result else None,
                error=runtime.error,
            ))

        return TestResult(
            testcase="",  # TODO: 从文件路径获取
            total_duration_ms=total_ms,
            steps=results,
        )
