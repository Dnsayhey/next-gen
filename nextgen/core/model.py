"""AST 模型定义 - DSL 的 Python 表示"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
class RequestNode:
    """HTTP 请求节点"""
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    # 请求体（互斥，同时出现会报错）
    json: dict[str, Any] | None = None
    form: dict[str, str] | None = None
    multipart: dict[str, str] | None = None
    body: str | None = None
    content_type: str | None = None
    timeout: float | None = None  # 请求超时（秒）

    def body_type(self) -> str | None:
        """获取请求体类型"""
        if self.json is not None:
            return "json"
        if self.form is not None:
            return "form"
        if self.multipart is not None:
            return "multipart"
        if self.body is not None:
            return "raw"
        return None


@dataclass
class AssertionNode:
    """断言节点"""
    op: str  # eq / ne / gt / lt / gte / lte / contains
    left: str  # 表达式（由 executor 解释）
    right: Any  # 期望值


@dataclass
class HookAction:
    """钩子动作"""
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestCaseHooks:
    """用例级钩子"""
    before_all: list[HookAction] = field(default_factory=list)
    after_all: list[HookAction] = field(default_factory=list)
    before_each: list[HookAction] = field(default_factory=list)
    after_each: list[HookAction] = field(default_factory=list)


@dataclass
class StepHooks:
    """步骤级钩子"""
    before: list[HookAction] = field(default_factory=list)
    after: list[HookAction] = field(default_factory=list)


@dataclass
class StepNode:
    """测试步骤节点"""
    name: str
    action_type: str  # "request" / "db" / "python" 等
    action_config: dict[str, Any]  # 原始 action 配置
    depends_on: list[str] = field(default_factory=list)
    extract: dict[str, str] = field(default_factory=dict)
    validate: list[AssertionNode] = field(default_factory=list)
    when: list | dict | None = None  # 条件执行（list=AND, dict=and/or）
    set_vars: dict[str, str] = field(default_factory=dict)  # 设置变量
    config: dict[str, Any] = field(default_factory=dict)
    hooks: StepHooks = field(default_factory=StepHooks)


@dataclass
class TestCase:
    """测试用例"""
    version: int
    steps: dict[str, StepNode]
    vars: dict[str, Any] = field(default_factory=dict)
    mode: str = "sequential"  # "sequential" | "parallel"
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)
    source_path: str | None = None
    base_dir: str | None = None


@dataclass
class StepResult:
    """步骤执行结果"""
    name: str
    status: StepStatus
    duration_ms: int
    request_summary: str  # e.g. "POST /login"
    response_status: int | None = None
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
