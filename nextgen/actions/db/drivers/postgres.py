"""PostgreSQL driver."""

from typing import Any
from urllib.parse import urlparse

import asyncpg
from loguru import logger


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute a PostgreSQL query.

    Args:
        url: Connection string, such as postgres://user:pass@host:5432/dbname.
        query: SQL query.
        params: Query parameters.

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    logger.debug(f"Connecting to PostgreSQL: {host}:{port}/{database}")

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
