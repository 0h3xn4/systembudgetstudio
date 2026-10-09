"""IBM Carbon theme (white and g100) with bundled IBM Plex fonts. No web resources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class CarbonTokens:
    background: str
    layer: str
    border: str
    text: str
    text_secondary: str
    interactive: str
    interactive_text: str


WHITE = CarbonTokens("#ffffff", "#f4f4f4", "#e0e0e0", "#161616", "#525252", "#0f62fe", "#ffffff")
G100 = CarbonTokens("#161616", "#262626", "#393939", "#f4f4f4", "#c6c6c6", "#4589ff", "#ffffff")
THEMES = {"white": WHITE, "g100": G100}

_FONT_FILES = (
    "IBMPlexSans-Light.ttf",
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-SemiBold.ttf",
    "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-SemiBold.ttf",
)


def assets_dir() -> Path:
    """Locate bundled assets: installed wheel, source checkout or PyInstaller bundle."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "assets", here.parent.parent / "assets"):
        if (candidate / "fonts").is_dir():
            return candidate
    raise FileNotFoundError("Bundled assets folder not found; the installation is incomplete.")


def load_fonts() -> list[str]:
    """Register the bundled IBM Plex fonts; return the family names that loaded."""
    fonts = assets_dir() / "fonts"
    families: list[str] = []
    for name in _FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(fonts / name))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(set(families))


def stylesheet(t: CarbonTokens) -> str:
    return f"""
    QWidget {{ background: {t.background}; color: {t.text}; font-size: 14px; }}
    QMainWindow, QDialog {{ background: {t.background}; }}
    QStatusBar, QDockWidget::title {{ background: {t.layer}; color: {t.text_secondary}; }}
    QPushButton {{ background: {t.interactive}; color: {t.interactive_text};
                   border: none; padding: 10px 16px; }}
    QTableView, QTreeView, QLineEdit {{ background: {t.layer}; border: 1px solid {t.border}; }}
    QHeaderView::section {{ background: {t.layer}; border: none;
                            border-bottom: 1px solid {t.border}; padding: 6px; }}
    """


def apply_theme(app: QApplication, name: str = "white") -> None:
    load_fonts()
    app.setFont(QFont("IBM Plex Sans", 10))
    app.setStyleSheet(stylesheet(THEMES[name]))
