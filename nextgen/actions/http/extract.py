"""HTTP variable extraction."""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.actions.http.path import http_extract_value


def extract_variables(
    result: dict[str, Any],
    config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """Extract variables from an HTTP response.

    Supports JSONPath syntax:
    - $.data.token -> extract from body
    - $$.status_code -> status code
    - $$.headers.xxx -> HTTP response header
    """
    extracted = {}

    for var_name, rule in config.items():
        try:
            value = http_extract_value(result, rule)
            ctx.set(var_name, value)
            extracted[var_name] = value
            logger.debug(f"Extracted variable: {var_name} = {value}")

        except Exception as e:
            logger.error(f"Failed to extract variable: {var_name} = {rule}, error: {e}")
            extracted[var_name] = None
            ctx.set(var_name, None)

    return extracted
