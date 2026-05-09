"""cli.py 单元测试"""

from nextgen.cli import render_terminal_summary
from nextgen.core.result import (
    StepResult,
    StepStatus,
    TestResult as CaseRunResult,
    TestStatus as CaseRunStatus,
)


def test_render_terminal_summary_for_success_result():
    result = CaseRunResult(
        testcase="/tmp/case.yaml",
        total_duration_ms=1234,
        status=CaseRunStatus.SUCCESS,
        steps=[
            StepResult(
                name="health",
                status=StepStatus.SUCCESS,
                duration_ms=12,
                action_summary="GET /health",
                metric={"label": "status_code", "value": 200},
            )
        ],
    )

    assert render_terminal_summary(result) == "\n".join([
        "-- result --",
        "  case.yaml  success  1234ms",
        "  steps: 1 passed, 0 failed, 0 skipped",
    ])


def test_render_terminal_summary_lists_failed_steps_with_metric_and_error():
    result = CaseRunResult(
        testcase="case.yaml",
        total_duration_ms=42,
        status=CaseRunStatus.FAILED,
        steps=[
            StepResult(
                name="login",
                status=StepStatus.FAILED,
                duration_ms=12,
                action_summary="POST /login",
                metric={"label": "status_code", "value": 500},
                error="boom",
            ),
            StepResult(
                name="cleanup",
                status=StepStatus.SKIPPED,
                duration_ms=0,
                action_summary="DELETE /tmp",
            ),
        ],
    )

    assert render_terminal_summary(result) == "\n".join([
        "-- result --",
        "  case.yaml  failed  42ms",
        "  steps: 0 passed, 1 failed, 1 skipped",
        "",
        "  FAILED  login  POST /login  status_code=500  boom",
    ])


def test_render_terminal_summary_lists_failed_steps_without_metric():
    result = CaseRunResult(
        testcase="case.yaml",
        total_duration_ms=42,
        status=CaseRunStatus.FAILED,
        steps=[
            StepResult(
                name="verify",
                status=StepStatus.FAILED,
                duration_ms=12,
                action_summary="GET /health",
                error="timeout",
            ),
        ],
    )

    assert "FAILED  verify  GET /health  timeout" in render_terminal_summary(result)
