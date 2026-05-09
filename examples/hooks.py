from nextgen import hook


@hook("mask_token")
def mask_token(ctx, source="token", target="masked_token"):
    """Mask a context value for logging/demo purposes."""
    value = ctx.get(source)
    if not value:
        ctx.set(target, "")
        return

    text = str(value)
    ctx.set(target, f"{text[:2]}***{text[-2:]}" if len(text) > 4 else "***")
