"""DB 执行器"""

from nextgen.core.actions import ActionSpec, register_action

from nextgen.executors.db.client import execute_query
from nextgen.executors.db.config import validate_db_config
from nextgen.executors.db.extract import extract_variables
from nextgen.executors.db.validate import validate_result

register_action(ActionSpec(
    name="db",
    execute=execute_query,
    extract=extract_variables,
    validate=validate_result,
    validate_config=validate_db_config,
))

__all__ = ["execute_query", "extract_variables", "validate_result"]
