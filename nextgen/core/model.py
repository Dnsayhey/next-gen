"""AST model definitions for the DSL."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionNode:
    """Action node inside a step."""

    type: str
    config: Any


@dataclass
class AssertionNode:
    """Assertion node."""
    op: str  # eq / ne / gt / lt / gte / lte / contains / not_contains / starts_with / ends_with / in / not_in / matches / len_*
    left: str  # Expression interpreted by the action implementation.
    right: Any  # Expected value.


@dataclass
class ExprCondition:
    """Single condition expression."""

    op: str
    left: Any
    right: Any


@dataclass
class AndCondition:
    """AND condition."""

    items: list["ConditionNode"] = field(default_factory=list)


@dataclass
class OrCondition:
    """OR condition."""

    items: list["ConditionNode"] = field(default_factory=list)


ConditionNode = ExprCondition | AndCondition | OrCondition


@dataclass
class HookAction:
    """Hook action."""
    type: str
    params: Any = field(default_factory=dict)


@dataclass
class TestCaseHooks:
    """Testcase-level hooks."""
    before_all: list[HookAction] = field(default_factory=list)
    after_all: list[HookAction] = field(default_factory=list)
    before_each: list[HookAction] = field(default_factory=list)
    after_each: list[HookAction] = field(default_factory=list)


@dataclass
class StepHooks:
    """Step-level hooks."""
    before: list[HookAction] = field(default_factory=list)
    after: list[HookAction] = field(default_factory=list)


@dataclass
class StepNode:
    """Test step node."""
    name: str
    action: ActionNode
    depends_on: list[str] = field(default_factory=list)
    extract: dict[str, Any] = field(default_factory=dict)
    export: dict[str, Any] = field(default_factory=dict)
    validate: list[AssertionNode] = field(default_factory=list)
    when: ConditionNode | None = None
    set_vars: dict[str, str] = field(default_factory=dict)  # Variables to set.
    config: dict[str, Any] = field(default_factory=dict)
    hooks: StepHooks = field(default_factory=StepHooks)


@dataclass
class TestCase:
    """Testcase model."""
    version: int
    steps: dict[str, StepNode]
    vars: dict[str, Any] = field(default_factory=dict)
    mode: str = "sequential"  # "sequential" | "parallel"
    fail_fast: bool = True
    hooks: TestCaseHooks = field(default_factory=TestCaseHooks)
    source_path: str | None = None
    base_dir: str | None = None
