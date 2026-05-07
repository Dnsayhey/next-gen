"""HTTP 执行器"""

from nextgen.core.actions import ActionSpec, register_action

from .client import execute_request
from .config import validate_request_config
from .extract import extract_variables
from .validate import validate_response

register_action(ActionSpec(
    name="request",
    execute=execute_request,
    extract=extract_variables,
    validate=validate_response,
    validate_config=validate_request_config,
))

__all__ = ["execute_request", "extract_variables", "validate_response"]
