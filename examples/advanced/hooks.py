from nextgen import hook


@hook("mask_value")
def mask_value(ctx, source="token", target="masked_value"):
    value = ctx.get(source)
    if not value:
        ctx.set(target, "")
        return

    text = str(value)
    ctx.set(target, f"{text[:2]}***{text[-2:]}" if len(text) > 4 else "***")
