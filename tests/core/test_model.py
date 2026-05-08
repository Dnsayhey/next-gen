"""model.py 单元测试"""

from nextgen.core.model import (
    ActionNode,
    AssertionNode,
    HookAction,
    StepNode,
    StepHooks,
    StepStatus,
    TestStatus as CaseRunStatus,
    StepResult,
    TestCase as CaseModel,
    TestCaseHooks as CaseHookModel,
    TestResult as CaseRunResult,
)


class TestStepStatus:
    """测试 StepStatus 枚举"""

    def test_status_values(self):
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.SUCCESS == "success"
        assert StepStatus.FAILED == "failed"
        assert StepStatus.SKIPPED == "skipped"
        assert StepStatus.RETRYING == "retrying"


class TestAssertionNode:
    """测试 AssertionNode"""

    def test_assertion_creation(self):
        node = AssertionNode(op="eq", left="$.code", right=0)
        assert node.op == "eq"
        assert node.left == "$.code"
        assert node.right == 0


class TestStepNode:
    """测试 StepNode"""

    def test_step_creation(self):
        step = StepNode(
            name="test_step",
            action=ActionNode(
                type="request",
                config={"method": "GET", "url": "http://test.com"},
            ),
        )
        assert step.name == "test_step"
        assert step.action.type == "request"
        assert step.action.config == {"method": "GET", "url": "http://test.com"}
        assert step.depends_on == []
        assert step.extract == {}
        assert step.validate == []
        assert step.config == {}
        assert step.hooks == StepHooks()


class TestCaseModel:
    """测试 TestCase"""

    def test_testcase_creation(self):
        step = StepNode(
            name="test_step",
            action=ActionNode(
                type="request",
                config={"method": "GET", "url": "http://test.com"},
            ),
        )
        testcase = CaseModel(
            version=1,
            steps={"test_step": step},
            vars={"base_url": "http://test.com"},
        )
        assert testcase.version == 1
        assert len(testcase.steps) == 1
        assert testcase.vars["base_url"] == "http://test.com"
        assert testcase.hooks == CaseHookModel()
        assert testcase.source_path is None
        assert testcase.base_dir is None


class TestHooksModel:
    """测试 hook 数据模型"""

    def test_hook_action_creation(self):
        action = HookAction(type="log", params={"message": "hello"})
        assert action.type == "log"
        assert action.params == {"message": "hello"}


class TestStepResult:
    """测试 StepResult"""

    def test_step_result_creation(self):
        result = StepResult(
            name="test_step",
            status=StepStatus.SUCCESS,
            duration_ms=100,
            action_summary="GET http://test.com",
        )
        assert result.name == "test_step"
        assert result.status == StepStatus.SUCCESS
        assert result.duration_ms == 100
        assert result.response_status is None
        assert result.error is None


class TestCaseResult:
    """测试 TestResult"""

    def test_summary(self):
        steps = [
            StepResult(name="s1", status=StepStatus.SUCCESS, duration_ms=100, action_summary="GET /"),
            StepResult(name="s2", status=StepStatus.FAILED, duration_ms=200, action_summary="POST /"),
            StepResult(name="s3", status=StepStatus.SKIPPED, duration_ms=0, action_summary="GET /"),
        ]
        result = CaseRunResult(
            testcase="test.yaml",
            total_duration_ms=300,
            steps=steps,
            status=CaseRunStatus.FAILED,
        )
        summary = result.summary
        assert summary["total"] == 3
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert result.status == CaseRunStatus.FAILED
