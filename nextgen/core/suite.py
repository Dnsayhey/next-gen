"""Suite execution orchestration."""

import time
from pathlib import Path

from nextgen.core.model import Suite
from nextgen.core.planner import validate_testcase
from nextgen.core.result import StepResult, StepStatus, SuiteResult, TestResult, TestStatus
from nextgen.core.scheduler import Scheduler
from nextgen.parser.env_loader import load_env_files
from nextgen.parser.loader import load_testcase


class SuiteRunner:
    """Run setup and testcase files as an isolated suite."""

    def __init__(
        self,
        suite: Suite,
        *,
        cli_env_files: list[Path] | None = None,
        max_concurrency: int = 10,
    ):
        self.suite = suite
        self.cli_env_files = cli_env_files or []
        self.max_concurrency = max_concurrency

    async def run(self) -> SuiteResult:
        """Run the suite sequentially."""
        start_time = time.monotonic()
        tests: list[TestResult] = []
        errors: list[str] = []
        setup_exports: dict[str, object] = {}

        suite_env = load_env_files(self.suite.env)
        cli_env = load_env_files(self.cli_env_files)

        for path in self.suite.setup:
            result = await self._run_testcase(path, {**suite_env, **cli_env})
            tests.append(result)
            if result.status == TestStatus.FAILED:
                errors.append(f"setup failed: {Path(path).name}")
                tests.extend(self._skipped_results(self.suite.tests, "skipped because suite setup failed"))
                return self._build_result(start_time, tests, errors)
            setup_exports.update(self._collect_exports(result))

        normal_env = {**suite_env, **setup_exports, **cli_env}
        for path in self.suite.tests:
            tests.append(await self._run_testcase(path, normal_env))

        return self._build_result(start_time, tests, errors)

    async def _run_testcase(self, path: str, env: dict[str, object]) -> TestResult:
        start_time = time.monotonic()
        try:
            testcase = load_testcase(path)
            testcase.vars = {**testcase.vars, **env}
            validate_testcase(testcase)

            result = await Scheduler(testcase, max_concurrency=self.max_concurrency).run()
            result.testcase = str(path)
            return result
        except Exception as exc:
            error = str(exc)
            return TestResult(
                testcase=str(path),
                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                steps=[
                    StepResult(
                        name="testcase",
                        status=StepStatus.FAILED,
                        duration_ms=0,
                        action_summary="load/validate/run testcase",
                        error=error,
                    )
                ],
                status=TestStatus.FAILED,
                errors=[error],
            )

    def _build_result(
        self,
        start_time: float,
        tests: list[TestResult],
        errors: list[str],
    ) -> SuiteResult:
        status = (
            TestStatus.FAILED
            if errors or any(test.status == TestStatus.FAILED for test in tests)
            else TestStatus.SUCCESS
        )
        return SuiteResult(
            suite=self.suite.name,
            total_duration_ms=int((time.monotonic() - start_time) * 1000),
            tests=tests,
            status=status,
            errors=errors,
        )

    def _skipped_results(self, paths: list[str], error: str) -> list[TestResult]:
        return [
            TestResult(
                testcase=str(path),
                total_duration_ms=0,
                steps=[],
                status=TestStatus.SKIPPED,
                errors=[error],
            )
            for path in paths
        ]

    def _collect_exports(self, result: TestResult) -> dict[str, object]:
        exports: dict[str, object] = {}
        for step in result.steps:
            if step.status == StepStatus.SUCCESS:
                exports.update(step.exported)
        return exports
