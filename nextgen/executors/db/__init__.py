"""DB action 实现"""

from nextgen.core.actions import ActionSpec, register_action

from nextgen.executors.db.client import execute_query
from nextgen.executors.db.extract import extract_variables
from nextgen.executors.db.model import DbConfig
from nextgen.executors.db.validate import validate_result

register_action(ActionSpec(
    name="db",
    parse_config=DbConfig.from_dict,
    execute=execute_query,
    extract=extract_variables,
    validate=validate_result,
    summarize=lambda config: config.summary(),
))

__all__ = ["execute_query", "extract_variables", "validate_result"]
