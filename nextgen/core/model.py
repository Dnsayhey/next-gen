"""AST 模型定义 - DSL 的 Python 表示"""

from dataclasses import dataclass, field
from typing import Any

from nextgen.core.result import StepResult, StepStatus, TestResult, TestStatus


@dataclass
class ActionNode:
    """步骤中的 action 节点"""

    type: str
    config: Any


@dataclass
class AssertionNode:
    """断言节点"""
    op: str  # eq / ne / gt / lt / gte / lte / contains / not_contains / starts_with / ends_with / in / not_in / matches / len_*
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
    action: ActionNode
    depends_on: list[str] = field(default_factory=list)
    extract: dict[str, Any] = field(default_factory=dict)
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
    fail_fast: bool = True
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)
    source_path: str | None = None
    base_dir: str | None = None
