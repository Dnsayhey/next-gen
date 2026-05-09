"""MySQL driver."""

from typing import Any
from urllib.parse import urlparse, parse_qs

import aiomysql
from loguru import logger


async def execute(url: str, query: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute a MySQL query.

    Args:
        url: Connection string, such as mysql://user:pass@host:3306/dbname.
        query: SQL query.
        params: Query parameters.

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

    logger.debug(f"Connecting to MySQL: {db_config['host']}:{db_config['port']}/{db_config['db']}")

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
