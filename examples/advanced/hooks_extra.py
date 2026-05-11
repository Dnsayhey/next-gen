from nextgen import hook


@hook
def remember_phase(ctx, phase):
    ctx.set("remembered_phase", phase)
