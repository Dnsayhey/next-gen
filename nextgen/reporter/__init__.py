"""Reporter entrypoint."""

from nextgen.reporter.base import Reporter, get_reporter, list_reporters, register_reporter
from nextgen.reporter.junit_reporter import JUnitReporter
from nextgen.reporter.json_reporter import JsonReporter

__all__ = [
    "JUnitReporter",
    "JsonReporter",
    "Reporter",
    "get_reporter",
    "list_reporters",
    "register_reporter",
]
