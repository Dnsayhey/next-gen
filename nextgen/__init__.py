"""nextgen public API"""

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.actions import ActionSpec, register_action
from nextgen.core.hooks import hook

load_builtin_actions()

__all__ = ["ActionSpec", "hook", "register_action"]
