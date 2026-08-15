"""PostgreSQL driver."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import asyncpg
from loguru import logger


@dataclass
class PostgresResource:
    """Case-scoped PostgreSQL connection pool."""

    pool: asyncpg.Pool

    async def execute(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        async with self.pool.acquire() as conn:
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

    async def aclose(self) -> None:
        await self.pool.close()


async def create_resource(url: str, max_size: int) -> PostgresResource:
    """Create a case-scoped PostgreSQL connection pool."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    logger.debug(f"Connecting to PostgreSQL: {host}:{port}/{database}")

    pool = await asyncpg.create_pool(url, min_size=1, max_size=max_size)
    return PostgresResource(pool)
