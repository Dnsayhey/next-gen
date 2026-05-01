"""JSON 报告生成器"""

import json
from dataclasses import asdict
from typing import Any

from nextgen.core.model import StepStatus, TestResult


def to_json(result: TestResult, indent: int = 2) -> str:
    """将测试结果转换为 JSON 字符串"""

    def serialize(obj: Any) -> Any:
        if isinstance(obj, StepStatus):
            return obj.value
        return obj

    data = {
        "testcase": result.testcase,
        "total_duration_ms": result.total_duration_ms,
        "summary": result.summary,
        "steps": [
            {
                "name": s.name,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "request": s.request_summary,
                "error": s.error,
            }
            for s in result.steps
        ],
    }

    return json.dumps(data, indent=indent, ensure_ascii=False)
