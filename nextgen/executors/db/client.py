"""DB 执行器 - 统一入口"""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.executors.db.drivers import get_driver


async def execute_query(config: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """执行数据库查询

    Args:
        config: action_config，包含 url / query / params
        ctx: 变量上下文

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    url = config.get("url")
    query = config.get("query")

    if not url:
        raise ValueError("db 必须包含 url 字段")
    if not query:
        raise ValueError("db 必须包含 query 字段")

    # 渲染变量
    url = ctx.render(url)
    query = ctx.render(query)
    params = config.get("params", [])
    if params:
        params = [ctx.render(p) if isinstance(p, str) else p for p in params]

    logger.info(f"执行查询: {query[:100]}...")

    driver = get_driver(url)
    result = await driver.execute(url, query, params)

    logger.info(f"查询完成: 返回 {result['row_count']} 行")
    return result
