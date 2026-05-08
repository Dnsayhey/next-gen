"""MySQL 驱动"""

from typing import Any
from urllib.parse import urlparse, parse_qs

import aiomysql
from loguru import logger


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """执行 MySQL 查询

    Args:
        url: 连接字符串，如 mysql://user:pass@host:3306/dbname
        query: SQL 查询
        params: 查询参数

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    parsed = urlparse(url)
    db_config = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": parsed.path.lstrip("/"),
    }

    logger.debug(f"连接 MySQL: {db_config['host']}:{db_config['port']}/{db_config['db']}")

    conn = await aiomysql.connect(**db_config)
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            return {
                "rows": rows or [],
                "row_count": cursor.rowcount,
                "columns": columns,
            }
    finally:
        conn.close()
