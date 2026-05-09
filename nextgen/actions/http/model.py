"""Internal models for the HTTP action."""

from dataclasses import dataclass, field
from typing import Any

from nextgen.core.errors import ParseError


@dataclass
class RequestConfig:
    """HTTP request action configuration."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    # Request bodies are mutually exclusive.
    json: dict[str, Any] | None = None
    form: dict[str, str] | None = None
    multipart: dict[str, str] | None = None
    body: str | None = None
    content_type: str | None = None
    timeout: float | None = None  # Request timeout in seconds.

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "RequestConfig":
        """Parse request configuration."""
        if "method" not in config:
            raise ParseError("request must include a method field")
        if "url" not in config:
            raise ParseError("request must include a url field")

        body_fields = [
            f for f in ["json", "form", "multipart", "body"]
            if config.get(f) is not None
        ]
        if len(body_fields) > 1:
            raise ParseError("json/form/multipart/body are mutually exclusive; choose only one")

        return cls(
            method=config.get("method", "").upper(),
            url=config.get("url", ""),
            headers=config.get("headers", {}),
            params=config.get("params", {}),
            json=config.get("json"),
            form=config.get("form"),
            multipart=config.get("multipart"),
            body=config.get("body"),
            content_type=config.get("content_type"),
            timeout=config.get("timeout"),
        )

    def body_type(self) -> str | None:
        """Return the request body type."""
        if self.json is not None:
            return "json"
        if self.form is not None:
            return "form"
        if self.multipart is not None:
            return "multipart"
        if self.body is not None:
            return "raw"
        return None

    def summary(self) -> str:
        """Generate a request action summary."""
        return f"{self.method} {self.url}"
