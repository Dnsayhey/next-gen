"""Database drivers."""

from typing import Any, Awaitable, Callable, Protocol

from nextgen.actions.db.drivers import postgres, mysql, sqlite


class DbResource(Protocol):
    """Case-scoped database execution resource."""

    async def execute(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> dict[str, Any]: ...

    async def aclose(self) -> None: ...


class DbDriver(Protocol):
    """Database driver module protocol."""

    create_resource: Callable[[str, int], Awaitable[DbResource]]

# URL scheme -> driver mapping.
DRIVERS: dict[str, DbDriver] = {
    "postgres": postgres,
    "postgresql": postgres,
    "mysql": mysql,
    "sqlite": sqlite,
}


def get_driver(url: str) -> DbDriver:
    """Return the driver for a URL scheme."""
    scheme = url.split("://")[0].lower()
    if scheme not in DRIVERS:
        raise ValueError(f"unsupported database type: {scheme}; supported: {list(DRIVERS.keys())}")
    return DRIVERS[scheme]
