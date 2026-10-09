"""GUI entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

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
    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
