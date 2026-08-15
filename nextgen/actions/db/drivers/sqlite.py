"""SQLite driver."""

import asyncio
from dataclasses import dataclass, field
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


@dataclass
class SqliteResource:
    """Case-scoped serialized SQLite connection."""

    connection: aiosqlite.Connection
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def execute(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]:
        async with self.lock:
            cursor = None
            try:
                cursor = await self.connection.execute(query, params or [])
                rows = await cursor.fetchall() if cursor.description else []
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                row_dicts = [dict(row) for row in rows]

                if columns:
                    row_count = len(row_dicts)
                else:
                    row_count = max(cursor.rowcount, 0)

                await self.connection.commit()
                return {
                    "rows": row_dicts,
                    "row_count": row_count,
                    "columns": columns,
                }
            except Exception:
                await self.connection.rollback()
                raise
            finally:
                if cursor is not None:
                    await cursor.close()

    async def aclose(self) -> None:
        async with self.lock:
            await self.connection.close()


async def create_resource(url: str, max_size: int) -> SqliteResource:
    """Create a case-scoped SQLite connection."""
    db_path = resolve_db_path(url)

    logger.debug(f"Connecting to SQLite: {db_path}")

    connection = await aiosqlite.connect(db_path)
    connection.row_factory = aiosqlite.Row
    return SqliteResource(connection)
