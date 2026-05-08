"""HTTP action 实现"""

from nextgen.core.actions import ActionSpec, register_action

from .client import execute_request
from .config import parse_request_config, summarize_request
from .extract import extract_variables
from .validate import validate_response

register_action(ActionSpec(
    name="request",
    parse_config=parse_request_config,
    execute=execute_request,
    extract=extract_variables,
    validate=validate_response,
    summarize=summarize_request,
))

__all__ = ["execute_request", "extract_variables", "validate_response"]
