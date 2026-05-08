"""DB action 配置校验"""

from typing import Any

from nextgen.executors.db.model import DbConfig


def parse_db_config(config: dict[str, Any]) -> DbConfig:
    """解析 db 配置"""
    if "url" not in config:
        raise ValueError("db 必须包含 url 字段")
    if "query" not in config:
        raise ValueError("db 必须包含 query 字段")
    params = config.get("params", [])
    if not isinstance(params, list):
        raise ValueError("db.params 必须是 list")

    return DbConfig(
        url=config["url"],
        query=config["query"],
        params=params,
    )


def summarize_db(config: DbConfig) -> str:
    """生成 db action 摘要"""
    db_type = config.url.split("://")[0] if "://" in config.url else "db"
    return f"{db_type}: {config.query[:50]}"
