"""通用执行错误类型"""

from typing import Any


class ActionExecutionError(RuntimeError):
    """action 执行失败，携带已渲染的输入快照"""

    def __init__(self, message: str, action_input: dict[str, Any]):
        super().__init__(message)
        self.action_input = action_input
