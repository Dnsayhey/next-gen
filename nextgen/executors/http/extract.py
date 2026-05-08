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
    - $.headers.xxx → 从 HTTP 响应头提取
    - $.body.xxx → 从 body 命名空间提取
    """
    extracted = {}
    source = {
        "status_code": result.get("status_code"),
        "headers": result.get("headers", {}),
        "body": result.get("body", {}),
    }

    for var_name, rule in config.items():
        try:
            value = extract_value(source, rule)

            if value is None and _is_legacy_body_path(rule):
                value = extract_value(result.get("body", {}), rule)

            ctx.set(var_name, value)
            extracted[var_name] = value
            logger.debug(f"提取变量: {var_name} = {value}")

        except Exception as e:
            logger.error(f"提取变量失败: {var_name} = {rule}, 错误: {e}")
            extracted[var_name] = None
            ctx.set(var_name, None)

    return extracted


def _is_legacy_body_path(rule: Any) -> bool:
    """兼容旧写法：$.data.token 等未显式加 $.body 的路径仍从 body 读取。"""
    expr = rule.get("jsonpath") if isinstance(rule, dict) else rule
    return (
        isinstance(expr, str)
        and expr.startswith("$.")
        and not expr.startswith("$.body.")
        and not expr.startswith("$.headers.")
        and expr != "$.status_code"
    )
