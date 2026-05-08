"""PostgreSQL 驱动"""

from typing import Any

import asyncpg
from loguru import logger


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """执行 PostgreSQL 查询

    Args:
        url: 连接字符串，如 postgres://user:pass@host:5432/dbname
        query: SQL 查询
        params: 查询参数

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    logger.debug(f"连接 PostgreSQL: {url}")

    conn = await asyncpg.connect(url)
    try:
        if params:
            result = await conn.fetch(query, *params)
        else:
            result = await conn.fetch(query)

        rows = [dict(row) for row in result]
        columns = list(result[0].keys()) if result else []

        return {
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
        }
    finally:
        await conn.close()
