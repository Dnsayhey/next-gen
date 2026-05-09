from nextgen import register_hook


@register_hook("mask_token")
async def mask_token(ctx, params):
    """Mask a context value for logging/demo purposes."""
    source = str(params.get("source", "token"))
    target = str(params.get("target", "masked_token"))
    value = ctx.get(source)
    if not value:
        ctx.set(target, "")
        return

    text = str(value)
    ctx.set(target, f"{text[:2]}***{text[-2:]}" if len(text) > 4 else "***")
