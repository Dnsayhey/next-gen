"""变量上下文 - 管理测试执行过程中的变量"""

from copy import deepcopy
from typing import Any

from loguru import logger


class Context:
    """变量上下文

    变量作用域：局部优先（extract 覆盖全局同名变量）
    """

    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.vars: dict[str, Any] = initial or {}
        self.metadata: dict[str, Any] = metadata or {}

    def set(self, key: str, value: Any) -> None:
        """设置变量"""
        self.vars[key] = value
        logger.debug(f"设置变量: {key} = {value}")

    def get(self, key: str) -> Any | None:
        """获取变量"""
        return self.vars.get(key)

    def snapshot(self) -> dict[str, Any]:
        """获取当前上下文快照"""
        return deepcopy(self.vars)

    def derive(self, initial: dict[str, Any] | None = None) -> "Context":
        """基于当前上下文创建子上下文"""
        data = self.snapshot()
        if initial:
            data.update(initial)
        return Context(data, metadata=self.metadata)

    def merge(self, updates: dict[str, Any]) -> None:
        """批量合并变量"""
        for key, value in updates.items():
            self.set(key, value)

    def render(self, value: Any) -> Any:
        """渲染变量替换

        支持 ${var_name} 语法
        """
        if not isinstance(value, str):
            return value

        result = value
        for k, v in self.vars.items():
            placeholder = f"${{{k}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(v))

        return result

    def render_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """递归渲染字典中的变量"""
        rendered = {}
        for k, v in data.items():
            if isinstance(v, dict):
                rendered[k] = self.render_dict(v)
            elif isinstance(v, list):
                rendered[k] = [self.render(item) for item in v]
            else:
                rendered[k] = self.render(v)
        return rendered
