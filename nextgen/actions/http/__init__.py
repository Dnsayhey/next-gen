"""HTTP action implementation."""

from nextgen.core.actions import ActionSpec, register_action

from .client import execute_request
from .extract import extract_variables
from .model import RequestConfig
from .validate import validate_response

register_action(ActionSpec(
    name="request",
    parse_config=RequestConfig.from_dict,
    execute=execute_request,
    extract=extract_variables,
    validate=validate_response,
    summarize=lambda config: config.summary(),
))

__all__ = ["execute_request", "extract_variables", "validate_response"]
