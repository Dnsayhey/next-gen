"""cli.py unit tests"""

from typer.testing import CliRunner

from nextgen.cli import app
from nextgen.cli import render_terminal_summary
from nextgen.core.result import (
    StepResult,
    StepStatus,
    TestResult as CaseRunResult,
    TestStatus as CaseRunStatus,
)


runner = CliRunner()


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


def test_run_reports_parse_error_without_traceback(tmp_path):
    case_file = tmp_path / "bad.yaml"
    case_file.write_text("version: 1\nsteps: {}\n", encoding="utf-8")

    result = runner.invoke(app, [str(case_file)])

    assert result.exit_code == 2
    assert "missing steps field or steps is empty" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_keeps_stdout_json_clean_when_non_verbose(tmp_path):
    case_file = tmp_path / "bad.yaml"
    case_file.write_text("version: 1\nsteps: {}\n", encoding="utf-8")

    result = runner.invoke(app, [str(case_file)])

    assert result.stdout == ""


def test_run_env_file_overrides_testcase_vars(tmp_path, monkeypatch):
    case_file = tmp_path / "case.yaml"
    case_file.write_text(
        "\n".join([
            "version: 1",
            "vars:",
            "  base_url: https://default.example.com",
            "steps:",
            "  one:",
            "    request:",
            "      method: GET",
            "      url: ${base_url}/get",
        ]),
        encoding="utf-8",
    )
    env_file = tmp_path / "staging.yaml"
    env_file.write_text("base_url: https://staging.example.com\n", encoding="utf-8")
    captured = {}

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            captured["vars"] = testcase.vars

        async def run(self):
            return CaseRunResult(
                testcase="case.yaml",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.cli.Scheduler", FakeScheduler)

    result = runner.invoke(app, [str(case_file), "--env", str(env_file)])

    assert result.exit_code == 0
    assert captured["vars"] == {"base_url": "https://staging.example.com"}


def test_run_multiple_env_files_apply_in_order(tmp_path, monkeypatch):
    case_file = tmp_path / "case.yaml"
    case_file.write_text(
        "\n".join([
            "version: 1",
            "steps:",
            "  one:",
            "    request:",
            "      method: GET",
            "      url: ${base_url}/get",
        ]),
        encoding="utf-8",
    )
    base_env = tmp_path / "base.yaml"
    override_env = tmp_path / "override.yaml"
    base_env.write_text("base_url: https://base.example.com\ntimeout: 3\n", encoding="utf-8")
    override_env.write_text("base_url: https://override.example.com\n", encoding="utf-8")
    captured = {}

    class FakeScheduler:
        def __init__(self, testcase, max_concurrency=10):
            captured["vars"] = testcase.vars

        async def run(self):
            return CaseRunResult(
                testcase="case.yaml",
                total_duration_ms=1,
                status=CaseRunStatus.SUCCESS,
                steps=[],
            )

    monkeypatch.setattr("nextgen.cli.Scheduler", FakeScheduler)

    result = runner.invoke(app, [
        str(case_file),
        "--env",
        str(base_env),
        "--env",
        str(override_env),
    ])

    assert result.exit_code == 0
    assert captured["vars"] == {
        "base_url": "https://override.example.com",
        "timeout": 3,
    }
