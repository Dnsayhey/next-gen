"""json_reporter.py 单元测试"""

import json

from nextgen.core.result import (
    StepResult,
    StepStatus,
    TestResult as CaseRunResult,
    TestStatus as CaseRunStatus,
)
from nextgen.reporter.json_reporter import to_json


def test_to_json_includes_testcase_status_errors_and_response_status():
    result = CaseRunResult(
        testcase="case.yaml",
        total_duration_ms=42,
        status=CaseRunStatus.FAILED,
        errors=["after_all failed"],
        steps=[
            StepResult(
                name="login",
                status=StepStatus.FAILED,
                duration_ms=12,
                action_summary="POST /login",
                response_status=500,
                action_input={
                    "type": "http",
                    "method": "POST",
                    "url": "https://example.com/login",
                    "headers": {"Authorization": "Bearer abc123"},
                    "params": {},
                    "body_type": "json",
                    "body": {"password": "secret"},
                    "timeout": None,
                },
                action_output={
                    "status_code": 500,
                    "headers": {"content-type": "application/json"},
                    "body": {"code": 1, "message": "boom"},
                },
                error="boom",
                extracted={"token": "abc123"},
            )
        ],
    )

    data = json.loads(to_json(result))

    assert data["status"] == "failed"
    assert data["errors"] == ["after_all failed"]
    assert data["steps"][0]["action"] == "POST /login"
    assert data["steps"][0]["response_status"] == 500
    assert data["steps"][0]["action_input"]["headers"]["Authorization"] == "Bearer abc123"
    assert data["steps"][0]["action_input"]["body"]["password"] == "secret"
    assert data["steps"][0]["action_output"]["status_code"] == 500
    assert data["steps"][0]["action_output"]["body"]["message"] == "boom"
    assert data["steps"][0]["extracted"] == {"token": "abc123"}


def test_to_json_serializes_success_result_with_summary():
    result = CaseRunResult(
        testcase="case.yaml",
        total_duration_ms=10,
        status=CaseRunStatus.SUCCESS,
        steps=[
            StepResult(
                name="health",
                status=StepStatus.SUCCESS,
                duration_ms=10,
                action_summary="GET /health",
                response_status=200,
            )
        ],
    )

    data = json.loads(to_json(result))

    assert data["status"] == "success"
    assert data["summary"] == {
        "total": 1,
        "success": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert data["steps"][0]["status"] == "success"
    assert data["steps"][0]["error"] is None
