"""json_reporter.py 单元测试"""

import json

from nextgen.core.model import (
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
                error="boom",
            )
        ],
    )

    data = json.loads(to_json(result))

    assert data["status"] == "failed"
    assert data["errors"] == ["after_all failed"]
    assert data["steps"][0]["action"] == "POST /login"
    assert data["steps"][0]["response_status"] == 500
