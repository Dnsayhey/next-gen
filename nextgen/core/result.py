"""Runtime execution result models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict


class ResultMetric(TypedDict):
    """Core summary metric for an action or step result.

    label uses a stable snake_case identifier, while value remains a JSON-friendly scalar.
    """

    label: str
    value: int | float | str | bool | None


@dataclass
class ActionResult:
    """Boundary object for action execution results."""

    data: dict[str, Any]
    action_input: dict[str, Any] | None = None
    action_output: dict[str, Any] | None = None
    metric: ResultMetric | None = None


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class TestStatus(str, Enum):
    """Testcase execution status."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class StepResult:
    """Step execution result."""

    name: str
    status: StepStatus
    duration_ms: int
    action_summary: str  # e.g. "POST /login" / "sqlite: SELECT ..."
    metric: ResultMetric | None = None
    action_input: dict[str, Any] | None = None
    action_output: dict[str, Any] | None = None
    error: str | None = None
    extracted: dict[str, Any] = field(default_factory=dict)
    exported: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Testcase execution result."""

    testcase: str  # File name.
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
