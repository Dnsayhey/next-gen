"""JSON report generator."""

import json
from dataclasses import dataclass

from nextgen.core.result import SuiteResult, TestResult
from nextgen.reporter.base import register_reporter


@dataclass(frozen=True)
class JsonReporter:
    """JSON reporter."""

    indent: int = 2
    name: str = "json"

    def render(self, result: TestResult | SuiteResult) -> str:
        if isinstance(result, SuiteResult):
            data = {
                "suite": result.suite,
                "status": result.status.value,
                "total_duration_ms": result.total_duration_ms,
                "summary": result.summary,
                "errors": result.errors,
                "tests": [self._render_test(test) for test in result.tests],
            }
        else:
            data = self._render_test(result)

        return json.dumps(data, indent=self.indent, ensure_ascii=False)

    def _render_test(self, result: TestResult) -> dict:
        return {
            "testcase": result.testcase,
            "status": result.status.value if result.status else None,
            "total_duration_ms": result.total_duration_ms,
            "summary": result.summary,
            "errors": result.errors,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "action": s.action_summary,
                    "metric": s.metric,
                    "action_input": s.action_input,
                    "action_output": s.action_output,
                    "error": s.error,
                    "extracted": s.extracted,
                    "exported": s.exported,
                }
                for s in result.steps
            ],
        }


register_reporter(JsonReporter())
