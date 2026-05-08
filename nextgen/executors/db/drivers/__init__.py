"""数据库驱动"""

from typing import Any, Protocol

from nextgen.executors.db.drivers import postgres, mysql, sqlite


class DbDriver(Protocol):
    """数据库驱动模块接口"""

    async def execute(
        self,
        url: str,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        ...

# URL scheme → 驱动映射
DRIVERS: dict[str, DbDriver] = {
    "postgres": postgres,
    "postgresql": postgres,
    "mysql": mysql,
    "sqlite": sqlite,
}


def get_driver(url: str) -> DbDriver:
    """根据 URL scheme 获取对应的驱动"""
    scheme = url.split("://")[0].lower()
    if scheme not in DRIVERS:
        raise ValueError(f"不支持的数据库类型: {scheme}，支持: {list(DRIVERS.keys())}")
    return DRIVERS[scheme]
