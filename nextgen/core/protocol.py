"""Action 和 Executor 协议定义"""

from typing import Any, Protocol


class Action(Protocol):
    """Action 配置协议"""

    def validate_config(self) -> None:
        """验证配置是否合法"""
        ...


class Executor(Protocol):
    """Executor 执行协议"""

    async def execute(self, action_config: dict[str, Any], ctx: 'Context') -> dict[str, Any]:
        """执行 action，返回结果"""
        ...

    def extract(self, result: dict[str, Any], config: dict[str, str], ctx: 'Context') -> dict[str, Any]:
        """从结果中提取变量，返回提取的变量字典"""
        ...

    def validate(self, result: dict[str, Any], assertions: list['AssertionNode']) -> list[str]:
        """验证结果，返回错误列表"""
        ...
