"""DB action 内部模型"""

from dataclasses import dataclass, field
from typing import Any

from nextgen.core.errors import ParseError


@dataclass
class DbConfig:
    """DB action 配置"""

    url: str
    query: str
    params: list[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "DbConfig":
        """解析 db 配置"""
        if "url" not in config:
            raise ParseError("db 必须包含 url 字段")
        if "query" not in config:
            raise ParseError("db 必须包含 query 字段")
        params = config.get("params", [])
        if not isinstance(params, list):
            raise ParseError("db.params 必须是 list")

        return cls(
            url=config["url"],
            query=config["query"],
            params=params,
        )

    def summary(self) -> str:
        """生成 db action 摘要"""
        db_type = self.url.split("://")[0] if "://" in self.url else "db"
        return f"{db_type}: {self.query[:50]}"
