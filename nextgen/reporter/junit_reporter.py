"""JUnit XML report generator."""

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from nextgen.core.result import StepResult, StepStatus, SuiteResult, TestResult, TestStatus
from nextgen.reporter.base import register_reporter


@dataclass(frozen=True)
class JUnitReporter:
    """JUnit XML reporter."""

    name: str = "junit"

    def render(self, result: TestResult | SuiteResult) -> str:
        root = ET.Element("testsuites")

        if isinstance(result, SuiteResult):
            root.append(self._render_suite(result.suite, result.tests, result.total_duration_ms))
        else:
            root.append(self._render_testcase_result(result))

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def _render_suite(
        self,
        name: str,
        tests: list[TestResult],
        duration_ms: int,
    ) -> ET.Element:
        suite = ET.Element("testsuite", {
            "name": name,
            "tests": str(sum(self._case_count(test) for test in tests)),
            "failures": str(sum(self._failure_count(test) for test in tests)),
            "errors": "0",
            "skipped": str(sum(self._skipped_count(test) for test in tests)),
            "time": self._seconds(duration_ms),
        })

        for test in tests:
            suite.extend(self._render_testcases(test))

        return suite

    def _render_testcase_result(self, result: TestResult) -> ET.Element:
        suite = self._render_suite(
            self._testcase_name(result),
            [result],
            result.total_duration_ms,
        )
        return suite

    def _render_testcases(self, result: TestResult) -> list[ET.Element]:
        if result.steps:
            return [
                self._render_step_case(result, step)
                for step in result.steps
            ]

        return [self._render_file_case(result)]

    def _render_step_case(self, result: TestResult, step: StepResult) -> ET.Element:
        case = ET.Element("testcase", {
            "classname": self._testcase_name(result),
            "name": step.name,
            "time": self._seconds(step.duration_ms),
        })

        if step.status == StepStatus.FAILED:
            failure = ET.SubElement(case, "failure", {
                "message": step.error or "step failed",
                "type": "failure",
            })
            failure.text = self._failure_text(result, step)
        elif step.status == StepStatus.SKIPPED:
            ET.SubElement(case, "skipped", {
                "message": step.error or "step skipped",
            })

        return case

    def _render_file_case(self, result: TestResult) -> ET.Element:
        case = ET.Element("testcase", {
            "classname": self._testcase_name(result),
            "name": self._testcase_name(result),
            "time": self._seconds(result.total_duration_ms),
        })

        if result.status == TestStatus.FAILED:
            failure = ET.SubElement(case, "failure", {
                "message": result.errors[0] if result.errors else "testcase failed",
                "type": "failure",
            })
            failure.text = "\n".join(result.errors)
        elif result.status == TestStatus.SKIPPED:
            ET.SubElement(case, "skipped", {
                "message": result.errors[0] if result.errors else "testcase skipped",
            })

        return case

    def _case_count(self, result: TestResult) -> int:
        return len(result.steps) if result.steps else 1

    def _failure_count(self, result: TestResult) -> int:
        if result.steps:
            return sum(1 for step in result.steps if step.status == StepStatus.FAILED)
        return 1 if result.status == TestStatus.FAILED else 0

    def _skipped_count(self, result: TestResult) -> int:
        if result.steps:
            return sum(1 for step in result.steps if step.status == StepStatus.SKIPPED)
        return 1 if result.status == TestStatus.SKIPPED else 0

    def _testcase_name(self, result: TestResult) -> str:
        return Path(result.testcase).name if result.testcase else "testcase"

    def _failure_text(self, result: TestResult, step: StepResult) -> str:
        lines = [
            f"testcase: {result.testcase}",
            f"step: {step.name}",
            f"action: {step.action_summary}",
        ]
        if step.metric is not None:
            lines.append(f"{step.metric['label']}: {step.metric['value']}")
        if step.error:
            lines.append(f"error: {step.error}")
        return "\n".join(lines)

    def _seconds(self, duration_ms: int) -> str:
        return f"{duration_ms / 1000:.3f}"


register_reporter(JUnitReporter())
