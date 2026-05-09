"""DB result variable extraction."""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.extract import extract_value


def extract_variables(
    result: dict[str, Any],
    config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """Extract variables from a query result.

    Supports JSONPath syntax:
    - $.rows[0].name -> extract from rows
    - $.row_count -> row count
    - $.columns -> column names

    Args:
        result: Query result {"rows": [...], "row_count": int, "columns": [...]}
        config: Extraction config {"var_name": "$.path"}
        ctx: Variable context.

    Returns:
        Extracted variables.
    """
    extracted = {}

    for var_name, rule in config.items():
        try:
            value = extract_value(result, rule)
            extracted[var_name] = value
            ctx.set(var_name, value)
            logger.debug(f"Extracted variable: {var_name} = {value}")
        except Exception as e:
            logger.warning(f"Failed to extract variable: {var_name} ({rule}): {e}")
            extracted[var_name] = None
            ctx.set(var_name, None)

    return extracted
