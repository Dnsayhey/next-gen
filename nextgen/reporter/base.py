"""Reporter protocol and registry."""

from __future__ import annotations

from typing import Protocol

from nextgen.core.result import TestResult


class Reporter(Protocol):
    """Test result reporter protocol."""

    name: str

    def render(self, result: TestResult) -> str:
        ...


REPORTER_REGISTRY: dict[str, Reporter] = {}


def register_reporter(reporter: Reporter) -> None:
    """Register a reporter implementation."""
    REPORTER_REGISTRY[reporter.name] = reporter


def get_reporter(name: str) -> Reporter | None:
    """Get a reporter implementation."""
    return REPORTER_REGISTRY.get(name)


def list_reporters() -> list[str]:
    """List registered reporter names."""
    return list(REPORTER_REGISTRY)
