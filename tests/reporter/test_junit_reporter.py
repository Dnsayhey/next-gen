"""junit_reporter.py unit tests"""

import xml.etree.ElementTree as ET

from nextgen.core.result import (
    StepResult,
    StepStatus,
    SuiteResult,
    TestResult as CaseRunResult,
    TestStatus as CaseRunStatus,
)
from nextgen.reporter import get_reporter, list_reporters
from nextgen.reporter.junit_reporter import JUnitReporter


def test_junit_reporter_serializes_testcase_steps():
    result = CaseRunResult(
        testcase="/tmp/case.yaml",
        total_duration_ms=42,
        status=CaseRunStatus.FAILED,
        steps=[
            StepResult(
                name="login",
                status=StepStatus.SUCCESS,
                duration_ms=10,
                action_summary="POST /login",
            ),
            StepResult(
                name="verify",
                status=StepStatus.FAILED,
                duration_ms=12,
                action_summary="GET /me",
                metric={"label": "status_code", "value": 500},
                error="boom",
            ),
            StepResult(
                name="cleanup",
                status=StepStatus.SKIPPED,
                duration_ms=0,
                action_summary="DELETE /session",
                error="dependency failed",
            ),
        ],
    )

    root = ET.fromstring(JUnitReporter().render(result))
    suite = root.find("testsuite")
    cases = root.findall("./testsuite/testcase")

    assert suite is not None
    assert suite.attrib["name"] == "case.yaml"
    assert suite.attrib["tests"] == "3"
    assert suite.attrib["failures"] == "1"
    assert suite.attrib["skipped"] == "1"
    assert cases[1].attrib == {
        "classname": "case.yaml",
        "name": "verify",
        "time": "0.012",
    }
    assert cases[1].find("failure").attrib["message"] == "boom"
    assert "status_code: 500" in cases[1].find("failure").text
    assert cases[2].find("skipped").attrib["message"] == "dependency failed"


def test_junit_reporter_serializes_suite_result():
    result = SuiteResult(
        suite="smoke",
        total_duration_ms=25,
        status=CaseRunStatus.FAILED,
        tests=[
            CaseRunResult(
                testcase="/tmp/pass.yaml",
                total_duration_ms=10,
                status=CaseRunStatus.SUCCESS,
                steps=[
                    StepResult(
                        name="health",
                        status=StepStatus.SUCCESS,
                        duration_ms=10,
                        action_summary="GET /health",
                    )
                ],
            ),
            CaseRunResult(
                testcase="/tmp/skip.yaml",
                total_duration_ms=0,
                status=CaseRunStatus.SKIPPED,
                steps=[],
                errors=["skipped because setup failed"],
            ),
        ],
    )

    root = ET.fromstring(JUnitReporter().render(result))
    suite = root.find("testsuite")
    cases = root.findall("./testsuite/testcase")

    assert suite is not None
    assert suite.attrib["name"] == "smoke"
    assert suite.attrib["tests"] == "2"
    assert suite.attrib["failures"] == "0"
    assert suite.attrib["skipped"] == "1"
    assert cases[0].attrib["classname"] == "pass.yaml"
    assert cases[1].attrib["name"] == "skip.yaml"
    assert cases[1].find("skipped").attrib["message"] == "skipped because setup failed"


def test_junit_reporter_serializes_file_level_failed_result():
    result = CaseRunResult(
        testcase="/tmp/bad.yaml",
        total_duration_ms=3,
        status=CaseRunStatus.FAILED,
        steps=[],
        errors=["invalid testcase format"],
    )

    root = ET.fromstring(JUnitReporter().render(result))
    suite = root.find("testsuite")
    case = root.find("./testsuite/testcase")
    failure = root.find("./testsuite/testcase/failure")

    assert suite is not None
    assert suite.attrib["tests"] == "1"
    assert suite.attrib["failures"] == "1"
    assert case is not None
    assert case.attrib == {
        "classname": "bad.yaml",
        "name": "bad.yaml",
        "time": "0.003",
    }
    assert failure is not None
    assert failure.attrib["message"] == "invalid testcase format"
    assert failure.text == "invalid testcase format"


def test_junit_reporter_implements_reporter_interface():
    assert "junit" in list_reporters()
    assert get_reporter("junit") is not None
