"""DB 执行器 - 统一入口"""

from loguru import logger

from nextgen.core.context import Context
from nextgen.executors.db.drivers import get_driver
from nextgen.executors.db.model import DbConfig


async def execute_query(config: DbConfig, ctx: Context) -> dict[str, object]:
    """执行数据库查询

    Args:
        config: db action 配置
        ctx: 变量上下文

    Returns:
        {"rows": [...], "row_count": int, "columns": [...]}
    """
    # 渲染变量
    url = ctx.render(config.url)
    query = ctx.render(config.query)
    params = config.params
    if params:
        params = [ctx.render(p) if isinstance(p, str) else p for p in params]

    logger.info(f"执行查询: {query[:100]}...")

    driver = get_driver(url)
    result = await driver.execute(url, query, params)

    logger.info(f"查询完成: 返回 {result['row_count']} 行")
    return result
