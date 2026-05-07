from nextgen import register_hook


@register_hook("seedVars")
async def seed_vars(ctx, params):
    """将参数中的键值写入当前上下文"""
    for key, value in params.items():
        ctx.set(key, value)
