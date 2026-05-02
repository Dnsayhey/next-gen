"""SQLite 驱动"""

from typing import Any
from urllib.parse import urlparse

import aiosqlite
from loguru import logger


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """执行 SQLite 查询

    Args:
        url: 连接字符串，如 sqlite:///path/to/db.sqlite
        query: SQL 查询
        params: 查询参数

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    # 解析路径：sqlite:///path/to/db → /path/to/db
    db_path = urlparse(url).path

    logger.debug(f"连接 SQLite: {db_path}")

    db = await aiosqlite.connect(db_path)
    try:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params or [])
        await db.commit()

        rows = await cursor.fetchall() if cursor.description else []
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        row_dicts = [dict(row) for row in rows]

        # rowcount: SELECT 用 len(rows)，INSERT/UPDATE/DELETE 用 cursor.rowcount，DDL 返回 0
        if columns:
            row_count = len(row_dicts)
        else:
            row_count = max(cursor.rowcount, 0)

        return {
            "rows": row_dicts,
            "row_count": row_count,
            "columns": columns,
        }
    finally:
        await db.close()
