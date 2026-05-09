"""Runtime built-in capability initialization."""


def load_builtin_actions() -> None:
    """Load built-in action plugins."""
    import nextgen.actions.db  # noqa: F401
    import nextgen.actions.http  # noqa: F401
