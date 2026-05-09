"""Database drivers."""

from typing import Any, Awaitable, Callable, Protocol

from nextgen.actions.db.drivers import postgres, mysql, sqlite


class DbDriver(Protocol):
    """Database driver module protocol."""

    execute: Callable[[str, str, list[Any] | None], Awaitable[dict[str, Any]]]

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
