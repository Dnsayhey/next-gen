"""nextgen package import tests."""

import importlib

from nextgen.core.actions import list_actions, restore_actions, snapshot_actions


def test_import_nextgen_does_not_load_builtin_actions():
    actions = snapshot_actions()
    restore_actions({})
    try:
        import nextgen

        importlib.reload(nextgen)

        assert list_actions() == []
    finally:
        restore_actions(actions)
