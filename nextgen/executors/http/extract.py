"""HTTP 变量提取"""

from typing import Any

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.extract import extract_value


def extract_variables(
    result: dict[str, Any],
    config: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    """从 HTTP 响应中提取变量

    支持 JSONPath 语法：
    - $.data.token → 从 body 提取
    - $.status_code → 状态码
    - $.headers.xxx → 从 body 中的 headers 字段提取
    """
    extracted = {}
    source = {
        "status_code": result.get("status_code"),
        "headers": result.get("headers", {}),
        "body": result.get("body", {}),
    }
    body = result.get("body", {})
    if isinstance(body, dict):
        source.update(body)

    for var_name, rule in config.items():
        try:
            value = extract_value(source, rule)

            ctx.set(var_name, value)
            extracted[var_name] = value
            logger.debug(f"提取变量: {var_name} = {value}")

        except Exception as e:
            logger.error(f"提取变量失败: {var_name} = {rule}, 错误: {e}")

    return extracted
