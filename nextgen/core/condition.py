"""Conditional execution evaluator."""

from loguru import logger

from nextgen.core.context import Context
from nextgen.core.model import AndCondition, ConditionNode, ExprCondition, OrCondition
from nextgen.core.operators import evaluate_operator


def evaluate_condition(condition: ConditionNode | None, ctx: Context) -> bool:
    """Evaluate whether a condition is satisfied.

    Args:
        condition: Condition AST node.
        ctx: Variable context.

    Returns:
        Whether the condition is satisfied.
    """
    if condition is None:
        return True

    if isinstance(condition, AndCondition):
        return all(evaluate_condition(item, ctx) for item in condition.items)
    if isinstance(condition, OrCondition):
        return any(evaluate_condition(item, ctx) for item in condition.items)
    return _eval_expr(condition, ctx)


def _eval_expr(expr: ExprCondition, ctx: Context) -> bool:
    """Evaluate a single expression."""
    left_expr = expr.left
    right_expr = expr.right

    left = ctx.render(left_expr)
    right = ctx.render(right_expr)

    result = evaluate_operator(expr.op, left, right)
    logger.debug(f"Condition evaluated: {left_expr} {expr.op} {right_expr} -> {result}")
    return result
