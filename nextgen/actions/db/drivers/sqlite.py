"""SQLite driver."""

from typing import Any
from urllib.parse import urlparse
from pathlib import Path

import aiosqlite
from loguru import logger


def resolve_db_path(url: str) -> str:
    """Resolve a SQLite URL path.

    - sqlite:///tmp/test.db -> /tmp/test.db
    - sqlite://./examples/test.db -> ./examples/test.db
    """
    parsed = urlparse(url)
    if parsed.netloc == ".":
        return str(Path("." + parsed.path))
    return parsed.path


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute a SQLite query.

    Args:
        url: Connection string, such as sqlite:///path/to/db.sqlite.
        query: SQL query.
        params: Query parameters.

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    db_path = resolve_db_path(url)

    logger.debug(f"Connecting to SQLite: {db_path}")

    db = await aiosqlite.connect(db_path)
    try:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params or [])
        await db.commit()

        rows = await cursor.fetchall() if cursor.description else []
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        row_dicts = [dict(row) for row in rows]

        # rowcount: SELECT uses len(rows), INSERT/UPDATE/DELETE uses cursor.rowcount, DDL returns 0.
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
