"""条件执行评估器"""

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.model import AndCondition, ConditionNode, ExprCondition, OrCondition
from nextgen.core.operators import evaluate_operator


def evaluate_condition(condition: ConditionNode | None, ctx: Context) -> bool:
    """评估条件是否满足

    Args:
        condition: 条件 AST 节点
        ctx: 变量上下文

    Returns:
        条件是否满足
    """
    if condition is None:
        return True

    if isinstance(condition, AndCondition):
        return all(evaluate_condition(item, ctx) for item in condition.items)
    if isinstance(condition, OrCondition):
        return any(evaluate_condition(item, ctx) for item in condition.items)
    return _eval_expr(condition, ctx)


def _eval_expr(expr: ExprCondition, ctx: Context) -> bool:
    """评估单个表达式"""
    left_expr = expr.left
    right_expr = expr.right

    left = ctx.render(left_expr)
    right = ctx.render(right_expr)

    result = evaluate_operator(expr.op, left, right)
    logger.debug(f"条件评估: {left_expr} {expr.op} {right_expr} → {result}")
    return result
