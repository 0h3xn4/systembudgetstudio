"""Empty main window shell; project tree, editors and Problems panel come in later milestones."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar

from budget_core import APP_NAME, __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        placeholder = QLabel(f"{APP_NAME}\nNo project open")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setObjectName("emptyState")
        self.setCentralWidget(placeholder)
        status = QStatusBar()
        status.showMessage(f"Version {__version__} — offline")
        self.setStatusBar(status)
