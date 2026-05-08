"""DB 结果变量提取"""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.extract import extract_value


def extract_variables(
    result: dict[str, Any],
    config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """从查询结果中提取变量

    支持 JSONPath 语法：
    - $.rows[0].name → 从行中提取
    - $.row_count → 行数
    - $.columns → 列名列表

    Args:
        result: 查询结果 {"rows": [...], "row_count": int, "columns": [...]}
        config: 提取配置 {"var_name": "$.path"}
        ctx: 变量上下文

    Returns:
        提取的变量字典
    """
    extracted = {}

    for var_name, rule in config.items():
        try:
            value = extract_value(result, rule)
            extracted[var_name] = value
            ctx.set(var_name, value)
            logger.debug(f"提取变量: {var_name} = {value}")
        except Exception as e:
            logger.warning(f"提取变量失败: {var_name} ({rule}): {e}")
            extracted[var_name] = None
            ctx.set(var_name, None)

    return extracted
