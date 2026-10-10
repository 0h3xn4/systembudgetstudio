"""An uncaught exception in the GUI becomes a plain message, never a traceback."""

from __future__ import annotations

import pytest

from budget_gui.app import describe_exception

pytestmark = pytest.mark.gui


def test_message_names_the_kind_but_not_the_content() -> None:
    try:
        raise ValueError("SECRETVALUE")
    except ValueError as exc:
        message = describe_exception(type(exc), exc)
    assert "ValueError" in message
    assert "SECRETVALUE" not in message and "Traceback" not in message
    assert "unsaved" not in message.lower() or "not" in message.lower()


def test_hook_is_installed_by_create_app(qtbot) -> None:  # type: ignore[no-untyped-def]
    import sys

    from budget_gui.app import create_app

    previous = sys.excepthook
    try:
        create_app(["x"])
        assert sys.excepthook is not sys.__excepthook__
    finally:
        sys.excepthook = previous
