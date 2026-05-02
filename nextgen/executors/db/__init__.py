"""DB 执行器"""

from nextgen.executors.db.client import execute_query
from nextgen.executors.db.extract import extract_variables
from nextgen.executors.db.validate import validate_result

__all__ = ["execute_query", "extract_variables", "validate_result"]
