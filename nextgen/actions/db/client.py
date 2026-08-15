"""DB action entrypoint."""

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError, describe_exception
from nextgen.core.result import ActionResult
from nextgen.actions.db.drivers import get_driver
from nextgen.actions.db.model import DbConfig

DB_RESOURCE_PREFIX = "db.resource:"


async def execute_query(config: DbConfig, ctx: Context) -> ActionResult:
    """Execute a database query.

    Args:
        config: DB action configuration.
        ctx: Variable context.

    Returns:
        ActionResult with DB result data and reporting snapshots.
    """
    # Render variables.
    url = ctx.render(config.url)
    query = ctx.render(config.query)
    params = config.params
    if params:
        params = [ctx.render(p) if isinstance(p, str) else p for p in params]

    action_input = {
        "type": "db",
        "url": url,
        "query": query,
        "params": params or [],
    }

    logger.info(f"Executing query: {query[:100]}...")

    driver = get_driver(url)
    try:
        max_size = ctx.metadata.get("max_concurrency", 10)
        resource = await ctx.get_or_create_resource(
            f"{DB_RESOURCE_PREFIX}{url}",
            lambda: driver.create_resource(url, max_size),
        )
        result = await resource.execute(query, params)
    except Exception as exc:
        raise ActionExecutionError(describe_exception(exc), action_input) from exc

    logger.info(f"Query completed: returned {result['row_count']} rows")
    return ActionResult(
        data=result,
        action_input=action_input,
        action_output={
            "row_count": result.get("row_count"),
            "columns": result.get("columns"),
            "rows": result.get("rows"),
        },
        metric={"label": "row_count", "value": result.get("row_count")},
    )
