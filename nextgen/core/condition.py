"""条件执行评估器"""

from typing import Any

from loguru import logger

from nextgen.core.context import Context


def evaluate_condition(condition: list | dict | None, ctx: Context) -> bool:
    """评估条件是否满足

    Args:
        condition: 条件表达式
            - None: 无条件，返回 True
            - list: 表达式列表，默认 AND
            - dict: {and: [...]} 或 {or: [...]}
        ctx: 变量上下文

    Returns:
        条件是否满足
    """
    if condition is None:
        return True

    if isinstance(condition, list):
        return _eval_and(condition, ctx)

    if isinstance(condition, dict):
        if "and" in condition:
            return _eval_and(condition["and"], ctx)
        if "or" in condition:
            return _eval_or(condition["or"], ctx)

    raise ValueError(f"未知的条件格式: {condition}")


def _eval_and(expressions: list, ctx: Context) -> bool:
    """评估 AND 条件（所有表达式都必须满足）"""
    for expr in expressions:
        if not _eval_item(expr, ctx):
            return False
    return True


def _eval_or(expressions: list, ctx: Context) -> bool:
    """评估 OR 条件（任一表达式满足即可）"""
    for expr in expressions:
        if _eval_item(expr, ctx):
            return True
    return False


def _eval_item(item: dict, ctx: Context) -> bool:
    """评估条件项（可能是嵌套条件或单个表达式）"""
    if not isinstance(item, dict):
        raise ValueError(f"条件项格式错误: {item}")

    # 嵌套条件
    if "and" in item:
        return _eval_and(item["and"], ctx)
    if "or" in item:
        return _eval_or(item["or"], ctx)

    # 单个表达式
    return _eval_expr(item, ctx)


def _eval_expr(expr: dict, ctx: Context) -> bool:
    """评估单个表达式"""
    if not isinstance(expr, dict) or len(expr) != 1:
        raise ValueError(f"表达式格式错误: {expr}")

    op = list(expr.keys())[0]
    args = expr[op]

    if not isinstance(args, list) or len(args) != 2:
        raise ValueError(f"表达式参数错误: {op} 需要两个参数 [left, right]")

    left_expr, right_expr = args

    left = _resolve_value(left_expr, ctx)
    right = _resolve_value(right_expr, ctx)

    result = _compare(op, left, right)
    logger.debug(f"条件评估: {left_expr} {op} {right_expr} → {result}")
    return result


def _resolve_value(expr: Any, ctx: Context) -> Any:
    """解析值，支持变量引用

    - 纯变量引用 ${var}：返回原始值（保留类型）
    - 混合字符串如 "prefix_${var}_suffix"：返回渲染后的字符串
    - 非字符串：直接返回
    """
    if not isinstance(expr, str):
        return expr

    # 纯变量引用
    if expr.startswith("${") and expr.endswith("}") and "${" not in expr[2:-1]:
        var_name = expr[2:-1]
        return ctx.get(var_name)

    # 混合字符串
    return ctx.render(expr)


def _compare(op: str, left: Any, right: Any) -> bool:
    """执行比较操作"""
    if op == "eq":
        return left == right
    elif op == "ne":
        return left != right
    elif op == "gt":
        return left > right
    elif op == "lt":
        return left < right
    elif op == "gte":
        return left >= right
    elif op == "lte":
        return left <= right
    elif op == "contains":
        return str(right) in str(left)
    else:
        raise ValueError(f"不支持的操作符: {op}")
