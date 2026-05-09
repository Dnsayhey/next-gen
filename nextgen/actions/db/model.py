"""Internal models for the DB action."""

from dataclasses import dataclass, field
from typing import Any

from nextgen.core.errors import ParseError


@dataclass
class DbConfig:
    """DB action configuration."""

    url: str
    query: str
    params: list[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "DbConfig":
        """Parse db configuration."""
        if "url" not in config:
            raise ParseError("db must include a url field")
        if "query" not in config:
            raise ParseError("db must include a query field")
        params = config.get("params", [])
        if not isinstance(params, list):
            raise ParseError("db.params must be a list")

        return cls(
            url=config["url"],
            query=config["query"],
            params=params,
        )

    def summary(self) -> str:
        """Generate a db action summary."""
        db_type = self.url.split("://")[0] if "://" in self.url else "db"
        return f"{db_type}: {self.query[:50]}"
