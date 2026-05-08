"""通用错误类型"""

from typing import Any


class NextgenError(Exception):
    """Nextgen 基础错误类型"""


class ParseError(NextgenError, ValueError):
    """测试用例或配置解析失败"""


class ExecutionError(NextgenError, RuntimeError):
    """执行阶段失败"""


class ValidationError(NextgenError, AssertionError):
    """断言或验证失败"""


class HookError(ExecutionError):
    """hook 执行失败"""


class ActionExecutionError(ExecutionError):
    """action 执行失败，携带已渲染的输入快照"""

    def __init__(self, message: str, action_input: dict[str, Any]):
        super().__init__(message)
        self.action_input = action_input
