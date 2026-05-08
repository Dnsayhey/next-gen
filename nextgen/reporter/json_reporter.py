"""JSON 报告生成器"""

import json

from nextgen.core.model import TestResult


def to_json(result: TestResult, indent: int = 2) -> str:
    """将测试结果转换为 JSON 字符串"""

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

    return json.dumps(data, indent=indent, ensure_ascii=False)
