"""DB 执行器"""

from nextgen.core.actions import ActionSpec, register_action

from nextgen.executors.db.client import execute_query
from nextgen.executors.db.config import parse_db_config, summarize_db
from nextgen.executors.db.extract import extract_variables
from nextgen.executors.db.validate import validate_result

register_action(ActionSpec(
    name="db",
    parse_config=parse_db_config,
    execute=execute_query,
    extract=extract_variables,
    validate=validate_result,
    summarize=summarize_db,
))

__all__ = ["execute_query", "extract_variables", "validate_result"]
