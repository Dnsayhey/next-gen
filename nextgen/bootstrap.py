"""运行时内置能力初始化"""


def load_builtin_actions() -> None:
    """加载内置 action 插件"""
    import nextgen.executors.db  # noqa: F401
    import nextgen.executors.http  # noqa: F401
