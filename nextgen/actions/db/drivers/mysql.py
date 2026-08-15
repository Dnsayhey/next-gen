"""MySQL driver."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import aiomysql
from loguru import logger


@dataclass
class MysqlResource:
    """Case-scoped MySQL connection pool."""

    pool: Any

    async def execute(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []

                    result = {
                        "rows": rows or [],
                        "row_count": cursor.rowcount,
                        "columns": columns,
                    }

                await conn.commit()
                return result
            except Exception:
                await conn.rollback()
                raise

    async def aclose(self) -> None:
        self.pool.close()
        await self.pool.wait_closed()


async def create_resource(url: str, max_size: int) -> MysqlResource:
    """Create a case-scoped MySQL connection pool."""
    parsed = urlparse(url)
    db_config = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": parsed.path.lstrip("/"),
    }

    logger.debug(f"Connecting to MySQL: {db_config['host']}:{db_config['port']}/{db_config['db']}")

    pool = await aiomysql.create_pool(
        **db_config,
        minsize=1,
        maxsize=max_size,
    )
    return MysqlResource(pool)
