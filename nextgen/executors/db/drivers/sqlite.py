"""SQLite 驱动"""

from typing import Any
from urllib.parse import urlparse
from pathlib import Path

import aiosqlite
from loguru import logger


def resolve_db_path(url: str) -> str:
    """解析 SQLite URL 路径。

    - sqlite:///tmp/test.db -> /tmp/test.db
    - sqlite://./examples/test.db -> ./examples/test.db
    """
    parsed = urlparse(url)
    if parsed.netloc == ".":
        return str(Path("." + parsed.path))
    return parsed.path


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """执行 SQLite 查询

    Args:
        url: 连接字符串，如 sqlite:///path/to/db.sqlite
        query: SQL 查询
        params: 查询参数

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    db_path = resolve_db_path(url)

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
