"""Common error types."""

from typing import Any


def describe_exception(exc: Exception) -> str:
    """Render an exception message that is never blank."""
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


class NextgenError(Exception):
    """Base error type for Nextgen."""


class ParseError(NextgenError, ValueError):
    """Testcase or configuration parsing failed."""


class ExecutionError(NextgenError, RuntimeError):
    """Execution failed."""


class ValidationError(NextgenError, AssertionError):
    """Assertion or validation failed."""


class HookError(ExecutionError):
    """Hook execution failed."""


class ReporterError(NextgenError):
    """Reporter selection or rendering failed."""


class ActionExecutionError(ExecutionError):
    """Action execution failed with the rendered input snapshot."""

    def __init__(self, message: str, action_input: dict[str, Any]):
        super().__init__(message)
        self.action_input = action_input
