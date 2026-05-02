"""数据库驱动"""

from nextgen.executors.db.drivers import postgres, mysql, sqlite

# URL scheme → 驱动映射
DRIVERS = {
    "postgres": postgres,
    "postgresql": postgres,
    "mysql": mysql,
    "sqlite": sqlite,
}


def get_driver(url: str):
    """根据 URL scheme 获取对应的驱动"""
    scheme = url.split("://")[0].lower()
    if scheme not in DRIVERS:
        raise ValueError(f"不支持的数据库类型: {scheme}，支持: {list(DRIVERS.keys())}")
    return DRIVERS[scheme]
