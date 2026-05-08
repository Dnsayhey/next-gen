"""运行时内置能力初始化"""


def load_builtin_actions() -> None:
    """加载内置 action 插件"""
    import nextgen.actions.db  # noqa: F401
    import nextgen.actions.http  # noqa: F401
