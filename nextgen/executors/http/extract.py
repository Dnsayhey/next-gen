"""HTTP 变量提取"""

from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse
from loguru import logger

from nextgen.core.context import Context


def extract_variables(
    result: dict[str, Any],
    config: dict[str, str],
    ctx: Context,
) -> dict[str, Any]:
    """从 HTTP 响应中提取变量

    支持 JSONPath 语法：
    - $.data.token → 从 body 提取
    - $.status_code → 状态码
    - $.headers.xxx → 从 body 中的 headers 字段提取
    """
    extracted = {}
    body = result.get("body", {})

    for var_name, jsonpath_expr in config.items():
        try:
            if jsonpath_expr == "$.status_code":
                value = result.get("status_code")
            elif jsonpath_expr.startswith("$.headers."):
                # 从 body 中的 headers 字段提取
                header_name = jsonpath_expr[10:]
                if isinstance(body, dict) and "headers" in body:
                    value = body["headers"].get(header_name)
                else:
                    value = None
            elif jsonpath_expr.startswith("$."):
                # 从 body 提取
                matches = jsonpath_parse(jsonpath_expr).find(body)
                value = matches[0].value if matches else None
            else:
                # 直接从 body 提取
                matches = jsonpath_parse(jsonpath_expr).find(body)
                value = matches[0].value if matches else None

            ctx.set(var_name, value)
            extracted[var_name] = value
            logger.debug(f"提取变量: {var_name} = {value}")

        except Exception as e:
            logger.error(f"提取变量失败: {var_name} = {jsonpath_expr}, 错误: {e}")

    return extracted
