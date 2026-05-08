"""JSON 报告生成器"""

import json
from dataclasses import dataclass

from nextgen.core.result import TestResult
from nextgen.reporter.base import register_reporter


@dataclass(frozen=True)
class JsonReporter:
    """JSON 报告器"""

    indent: int = 2
    name: str = "json"

    def render(self, result: TestResult) -> str:
        data = {
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
                    "response_status": s.response_status,
                    "action_input": s.action_input,
                    "action_output": s.action_output,
                    "error": s.error,
                    "extracted": s.extracted,
                }
                for s in result.steps
            ],
        }

        return json.dumps(data, indent=self.indent, ensure_ascii=False)


register_reporter(JsonReporter())
