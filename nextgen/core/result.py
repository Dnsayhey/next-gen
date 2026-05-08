"""运行时执行结果模型"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ActionResult:
    """action 执行结果边界对象"""

    data: dict[str, Any]
    action_input: dict[str, Any] | None = None
    action_output: dict[str, Any] | None = None
    summary_status: int | float | str | None = None


class StepStatus(str, Enum):
    """步骤执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class TestStatus(str, Enum):
    """测试用例执行状态"""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class StepResult:
    """步骤执行结果"""

    name: str
    status: StepStatus
    duration_ms: int
    action_summary: str  # e.g. "POST /login" / "sqlite: SELECT ..."
    response_status: int | float | str | None = None
    action_input: dict[str, Any] | None = None
    action_output: dict[str, Any] | None = None
    error: str | None = None
    extracted: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """测试用例执行结果"""

    testcase: str  # 文件名
    total_duration_ms: int
    steps: list[StepResult]
    status: TestStatus
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.steps),
            "success": sum(1 for s in self.steps if s.status == StepStatus.SUCCESS),
            "failed": sum(1 for s in self.steps if s.status == StepStatus.FAILED),
            "skipped": sum(1 for s in self.steps if s.status == StepStatus.SKIPPED),
        }
