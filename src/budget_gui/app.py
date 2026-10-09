"""GUI entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from budget_core import APP_NAME
from budget_gui.main_window import MainWindow
from budget_gui.theme import apply_theme


def create_app(argv: Sequence[str]) -> QApplication:
    app = QApplication.instance() or QApplication(list(argv))
    assert isinstance(app, QApplication)
    app.setApplicationName(APP_NAME)
    apply_theme(app)
    return app


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:  # Qt-free check of a packaged build
        from budget_core.selftest import run_selftest

        failures = run_selftest()
        print("Self-test passed." if not failures else "FAILED: " + "; ".join(failures))
        return 1 if failures else 0
    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    if args and not args[0].startswith("-"):
        window.open_project(Path(args[0]))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
