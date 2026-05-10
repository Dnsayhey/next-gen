"""nextgen public API"""

from nextgen.core.actions import ActionSpec, register_action
from nextgen.core.hooks import hook

__all__ = ["ActionSpec", "hook", "register_action"]
