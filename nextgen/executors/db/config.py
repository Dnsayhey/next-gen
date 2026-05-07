"""DB action 配置校验"""

from typing import Any


def validate_db_config(config: dict[str, Any]) -> None:
    """验证 db 配置"""
    if "url" not in config:
        raise ValueError("db 必须包含 url 字段")
    if "query" not in config:
        raise ValueError("db 必须包含 query 字段")
