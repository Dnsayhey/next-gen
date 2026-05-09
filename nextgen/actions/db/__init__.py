"""DB action implementation."""

from nextgen.core.actions import ActionSpec, register_action

from nextgen.actions.db.client import execute_query
from nextgen.actions.db.extract import extract_variables
from nextgen.actions.db.model import DbConfig
from nextgen.actions.db.validate import validate_result

register_action(ActionSpec(
    name="db",
    parse_config=DbConfig.from_dict,
    execute=execute_query,
    extract=extract_variables,
    validate=validate_result,
    summarize=lambda config: config.summary(),
))

__all__ = ["execute_query", "extract_variables", "validate_result"]
