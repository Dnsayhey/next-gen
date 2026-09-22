"""HTTP variable extraction."""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError
from nextgen.actions.http.path import http_extract_value


def extract_variables(
    result: dict[str, Any],
    config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """Extract variables from an HTTP response.

    Supports HTTP response path syntax:
    - $.data.token -> extract ``data.token`` from the response body
    - $$.status_code -> status code metadata
    - $$.headers.xxx -> HTTP response header metadata

    The ``$.`` root is the response body root; ``body`` is not an
    additional path segment. Use ``$$.`` for response metadata.
    """
    extracted = {}

    for var_name, rule in config.items():
        try:
            value = http_extract_value(result, rule)
            ctx.set(var_name, value)
            extracted[var_name] = value
            logger.debug(f"Extracted variable: {var_name} = {value}")

        except Exception as e:
            message = f"Failed to extract variable: {var_name} = {rule}, error: {e}"
            logger.error(message)
            raise ActionExecutionError(message, {"type": "http_extract", "variable": var_name, "rule": rule}) from e

    return extracted
