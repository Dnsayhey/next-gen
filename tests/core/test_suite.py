"""suite.py unit tests"""

import pytest

from nextgen.core.model import ActionNode, StepNode, Suite, TestCase as CaseModel
from nextgen.core.result import (
    StepResult,
    StepStatus,
    TestResult as CaseRunResult,
    TestStatus as CaseRunStatus,
)
from nextgen.core.suite import SuiteRunner


@pytest.mark.asyncio
async def test_suite_runner_applies_setup_exports_before_cli_env(monkeypatch):
    seen_vars = []

    def fake_load_testcase(path):
        return CaseModel(version=1, steps={}, source_path=str(path))

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            self.testcase = testcase
            seen_vars.append(testcase.vars.copy())

        async def run(self):
            if self.testcase.source_path.endswith("setup.yaml"):
                return CaseRunResult(
                    testcase="setup.yaml",
                    total_duration_ms=1,
                    status=CaseRunStatus.SUCCESS,
                    steps=[
                        StepResult(
                            name="login",
                            status=StepStatus.SUCCESS,
                            duration_ms=1,
                            action_summary="POST /login",
                            exported={"token": "setup-token"},
                        )
                    ],
                )
            return CaseRunResult(
                testcase="case.yaml",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        setup=["/tmp/setup.yaml"],
        tests=["/tmp/case.yaml"],
    )

    result = await SuiteRunner(suite, cli_env_files=[]).run()

    assert result.status == CaseRunStatus.SUCCESS
    assert seen_vars[0] == {}
    assert seen_vars[1]["token"] == "setup-token"


@pytest.mark.asyncio
async def test_suite_runner_cli_env_overrides_setup_exports(tmp_path, monkeypatch):
    cli_env = tmp_path / "cli.yaml"
    cli_env.write_text("token: cli-token\n", encoding="utf-8")
    seen_vars = []

    def fake_load_testcase(path):
        return CaseModel(version=1, steps={}, source_path=str(path))

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            self.testcase = testcase
            seen_vars.append(testcase.vars.copy())

        async def run(self):
            return CaseRunResult(
                testcase=self.testcase.source_path or "",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[
                    StepResult(
                        name="login",
                        status=StepStatus.SUCCESS,
                        duration_ms=1,
                        action_summary="POST /login",
                        exported={"token": "setup-token"},
                    )
                ] if self.testcase.source_path and self.testcase.source_path.endswith("setup.yaml") else [],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        setup=["/tmp/setup.yaml"],
        tests=["/tmp/case.yaml"],
    )

    await SuiteRunner(suite, cli_env_files=[cli_env]).run()

    assert seen_vars[0]["token"] == "cli-token"
    assert seen_vars[1]["token"] == "cli-token"


@pytest.mark.asyncio
async def test_suite_runner_skips_normal_tests_after_setup_failure(monkeypatch):
    def fake_load_testcase(path):
        return CaseModel(version=1, steps={}, source_path=str(path))

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            self.testcase = testcase

        async def run(self):
            return CaseRunResult(
                testcase="setup.yaml",
                total_duration_ms=1,
                status=CaseRunStatus.FAILED,
                steps=[],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        setup=["/tmp/setup.yaml"],
        tests=["/tmp/case.yaml", "/tmp/other.yaml"],
    )

    result = await SuiteRunner(suite).run()

    assert result.status == CaseRunStatus.FAILED
    assert result.summary == {"total": 3, "success": 0, "failed": 1, "skipped": 2}
    assert [test.status for test in result.tests] == [
        CaseRunStatus.FAILED,
        CaseRunStatus.SKIPPED,
        CaseRunStatus.SKIPPED,
    ]
    assert result.tests[1].testcase == "/tmp/case.yaml"


@pytest.mark.asyncio
async def test_suite_runner_keeps_running_after_normal_testcase_error(monkeypatch):
    loaded_paths = []

    def fake_load_testcase(path):
        loaded_paths.append(str(path))
        if str(path).endswith("bad.yaml"):
            raise ValueError("bad testcase")
        return CaseModel(version=1, steps={}, source_path=str(path))

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            self.testcase = testcase

        async def run(self):
            return CaseRunResult(
                testcase=self.testcase.source_path or "",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        tests=["/tmp/bad.yaml", "/tmp/good.yaml"],
    )

    result = await SuiteRunner(suite).run()

    assert loaded_paths == ["/tmp/bad.yaml", "/tmp/good.yaml"]
    assert result.status == CaseRunStatus.FAILED
    assert [test.status for test in result.tests] == [
        CaseRunStatus.FAILED,
        CaseRunStatus.SUCCESS,
    ]
    assert result.tests[0].errors == ["bad testcase"]
    assert result.tests[0].steps[0].status == StepStatus.FAILED


@pytest.mark.asyncio
async def test_suite_runner_applies_tag_filters_to_setup_and_tests(monkeypatch):
    seen_steps = []

    def fake_load_testcase(path):
        return CaseModel(
            version=1,
            source_path=str(path),
            steps={
                "login": StepNode(
                    name="login",
                    action=ActionNode(type="request", config={"method": "GET", "url": "https://example.com/login"}),
                    tags=["auth"],
                ),
                "profile": StepNode(
                    name="profile",
                    action=ActionNode(type="request", config={"method": "GET", "url": "https://example.com/profile"}),
                    depends_on=["login"],
                    tags=["smoke"],
                ),
                "audit": StepNode(
                    name="audit",
                    action=ActionNode(type="request", config={"method": "GET", "url": "https://example.com/audit"}),
                    tags=["slow"],
                ),
            },
        )

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            self.testcase = testcase
            seen_steps.append(list(testcase.steps))

        async def run(self):
            return CaseRunResult(
                testcase=self.testcase.source_path or "",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        setup=["/tmp/setup.yaml"],
        tests=["/tmp/case.yaml"],
    )

    result = await SuiteRunner(
        suite,
        include_tags={"smoke"},
        skip_tags={"slow"},
    ).run()

    assert result.status == CaseRunStatus.SUCCESS
    assert seen_steps == [["login", "profile"], ["login", "profile"]]


@pytest.mark.asyncio
async def test_suite_runner_keeps_runtime_resources_isolated_between_testcases(monkeypatch):
    resource_ids = []

    def fake_load_testcase(path):
        return CaseModel(version=1, steps={}, source_path=str(path))

    class FakeResource:
        async def aclose(self):
            pass

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            from nextgen.core.context import Context

            self.context = Context()

        async def run(self):
            resource = FakeResource()
            self.context.set_resource("http.client", resource)
            resource_ids.append(id(resource))
            await self.context.close_resources()
            return CaseRunResult(
                testcase="case.yaml",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.core.suite.load_testcase", fake_load_testcase)
    monkeypatch.setattr("nextgen.core.suite.Scheduler", FakeScheduler)
    suite = Suite(
        name="smoke",
        tests=["/tmp/one.yaml", "/tmp/two.yaml"],
    )

    result = await SuiteRunner(suite).run()

    assert result.status == CaseRunStatus.SUCCESS
    assert len(resource_ids) == 2
    assert resource_ids[0] != resource_ids[1]
