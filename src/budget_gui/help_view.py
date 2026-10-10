"""Help > User guide: the guide rendered inside the window (no browser, no network)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from budget_core.guide.build import build_guide
from budget_core.guide.html import render_html
from budget_core.model import Project

STEM = "system-budget-studio-guide"


class GuideDialog(QDialog):
    def __init__(self, project: Project | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("User guide")
        self.resize(980, 760)
        self.guide = build_guide(project)
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._anchor)
        self.browser.setHtml(render_html(self.guide, embed_fonts=False))
        self.status = QLabel("")
        save = QPushButton("Save as HTML and PDF…")
        save.clicked.connect(lambda: self._choose_folder())
        row = QHBoxLayout()
        row.addWidget(save)
        row.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser, 1)
        layout.addLayout(row)

    def _anchor(self, url) -> None:  # type: ignore[no-untyped-def]
        if url.hasFragment():  # only in-page links; nothing is ever opened externally
            self.browser.scrollToAnchor(url.fragment())

    def save_to(self, folder: Path) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        html = folder / f"{STEM}.html"
        html.write_text(render_html(self.guide), encoding="utf-8", newline="\n")
        # Imported here, not at module level: ReportLab pulls in networking modules (never used).
        from budget_core.guide.pdf import render_pdf

        pdf = folder / f"{STEM}.pdf"
        pdf.write_bytes(render_pdf(self.guide))
        self.status.setText(f"Saved {html.name} and {pdf.name}.")
        return [html, pdf]

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save the guide to folder")
        if folder:
            try:
                self.save_to(Path(folder))
            except OSError:
                self.status.setText("The guide could not be saved. Check the folder.")
