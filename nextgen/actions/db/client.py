"""DB action - 统一入口"""

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.errors import ActionExecutionError
from nextgen.core.result import ActionResult
from nextgen.actions.db.drivers import get_driver
from nextgen.actions.db.model import DbConfig


async def execute_query(config: DbConfig, ctx: Context) -> ActionResult:
    """执行数据库查询

    Args:
        config: db action 配置
        ctx: 变量上下文

    Returns:
        ActionResult with DB result data and reporting snapshots.
    """
    # 渲染变量
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

    logger.info(f"执行查询: {query[:100]}...")

    driver = get_driver(url)
    try:
        result = await driver.execute(url, query, params)
    except Exception as exc:
        raise ActionExecutionError(str(exc), action_input) from exc

    logger.info(f"查询完成: 返回 {result['row_count']} 行")
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
