"""Guided mode: a short wizard from project name and orbit to the first budget.

Five pages (project, spacecraft, orbit, scenario, review) with sensible defaults, so a first
budget needs a name and four clicks. The checks are the same ones the headless builder uses.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from budget_core.wizard import (
    MAX_DAYS,
    SAMPLES,
    Issue,
    WizardAnswers,
    WizardError,
    check_answers,
    create_project,
    folder_name,
)

PAGES = {
    "Project": ("project_name",),
    "Spacecraft": ("sample",),
    "Orbit": ("altitude_km", "inclination_deg", "raan_deg"),
    "Scenario": ("duration_days", "start_utc"),
}


class _Page(QWizardPage):
    def __init__(self, wizard: GuidedWizard, title: str, intro: str) -> None:
        super().__init__()
        self._wizard = wizard
        self.setTitle(title)
        self.setSubTitle(intro)
        self.form = QFormLayout()
        outer = QVBoxLayout(self)
        outer.addLayout(self.form)

    def isComplete(self) -> bool:  # noqa: N802 (Qt naming)
        return self._wizard.page_ok(self.title())

    def initializePage(self) -> None:  # noqa: N802 (Qt naming)
        self._wizard.refresh_error(self.title())


class GuidedWizard(QWizard):
    """Collects the answers and creates the project folder on Finish."""

    created = Signal(object)

    def __init__(self, parent_folder: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New project (guided mode)")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.parent_folder = Path(parent_folder)
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #da1e28;")  # Carbon red 60

        self.name_edit = QLineEdit("My first satellite")
        self.folder_edit = QLineEdit(str(self.parent_folder))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)

        self.sample_combo = QComboBox()
        for key, text in SAMPLES.items():
            self.sample_combo.addItem(text, key)
        self.altitude = self._spin(550.0, 1, " km", 0.0, 100000.0)
        self.inclination = self._spin(97.6, 1, " deg", 0.0, 180.0)
        self.raan = self._spin(100.0, 1, " deg", 0.0, 359.9)
        self.duration = self._spin(1.0, 2, " days", 0.01, 1000.0)
        self.start_edit = QLineEdit("2026-06-01T00:00:00Z")
        self.review = QLabel("")
        self.review.setWordWrap(True)

        project = _Page(self, "Project", "Name your project and choose where it is stored.")
        project.form.addRow("Project name", self.name_edit)
        project.form.addRow("Parent folder", folder_row)
        spacecraft = _Page(
            self,
            "Spacecraft",
            "Start from a sample spacecraft. Its numbers are invented; you replace them later.",
        )
        spacecraft.form.addRow("Sample", self.sample_combo)
        orbit = _Page(
            self,
            "Orbit",
            "A near-circular orbit. The altitude is above the Earth's surface.",
        )
        orbit.form.addRow("Altitude", self.altitude)
        orbit.form.addRow("Inclination", self.inclination)
        orbit.form.addRow("RAAN (ascending node)", self.raan)
        scenario = _Page(
            self,
            "Scenario",
            f"How long to simulate (up to {MAX_DAYS:g} days) and when it starts (UTC).",
        )
        scenario.form.addRow("Length", self.duration)
        scenario.form.addRow("Start (UTC)", self.start_edit)
        review = _Page(
            self,
            "Review",
            "Finish creates the project, opens it and computes the first power timeline.",
        )
        review.form.addRow(self.review)
        self._pages = {p.title(): p for p in (project, spacecraft, orbit, scenario, review)}
        for page in self._pages.values():
            self.addPage(page)
        # one shared error label moves with the current page
        self.currentIdChanged.connect(self._move_error_label)

        for widget in (self.name_edit, self.folder_edit, self.start_edit):
            widget.textChanged.connect(lambda _t: self._changed())
        for spin in (self.altitude, self.inclination, self.raan, self.duration):
            spin.valueChanged.connect(lambda _v: self._changed())
        self.sample_combo.currentIndexChanged.connect(lambda _i: self._changed())
        self.restart()  # makes the first page current and puts the error label on it

    @staticmethod
    def _spin(value: float, decimals: int, suffix: str, low: float, high: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(low, high)
        box.setSuffix(suffix)
        box.setValue(value)
        return box

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the parent folder")
        if folder:
            self.folder_edit.setText(folder)

    # ---- answers -----------------------------------------------------------------------------
    def answers(self) -> WizardAnswers:
        return WizardAnswers(
            project_name=self.name_edit.text(),
            sample=str(self.sample_combo.currentData()),
            altitude_km=self.altitude.value(),
            inclination_deg=self.inclination.value(),
            raan_deg=self.raan.value(),
            duration_days=self.duration.value(),
            start_utc=self.start_edit.text(),
        )

    def _target(self) -> Path:
        return Path(self.folder_edit.text().strip() or ".") / folder_name(self.name_edit.text())

    def issues_for(self, page: str) -> list[Issue]:
        fields = PAGES.get(page, ())
        issues = [i for i in check_answers(self.answers()) if i.field in fields]
        if page == "Project" and self._target().exists():
            issues.append(
                Issue(
                    "project_name",
                    f"The folder '{self._target().name}' already exists. "
                    "Choose another project name or folder.",
                )
            )
        return issues

    def page_ok(self, page: str) -> bool:
        return not self.issues_for(page)

    def refresh_error(self, page: str) -> None:
        issues = self.issues_for(page)
        self.error_label.setText(issues[0].message if issues else "")

    def _current_title(self) -> str:
        page = self.currentPage()
        return page.title() if page is not None else "Project"

    def _move_error_label(self, _id: int) -> None:
        page = self.currentPage()
        if page is None:
            return
        layout = page.layout()
        if layout is not None and self.error_label.parent() is not page:
            layout.addWidget(self.error_label)
        a = self.answers()
        self.review.setText(
            f"Project: {a.project_name.strip()}\n"
            f"Folder: {self._target()}\n"
            f"Sample: {SAMPLES.get(a.sample, '')}\n"
            f"Orbit: {a.altitude_km:g} km, inclination {a.inclination_deg:g} deg, "
            f"RAAN {a.raan_deg:g} deg\n"
            f"Scenario: {a.duration_days:g} day(s) from {a.start_utc.strip()}"
        )
        self.refresh_error(page.title())

    def _changed(self) -> None:
        title = self._current_title()
        self.refresh_error(title)
        page = self.currentPage()
        if page is not None:
            page.completeChanged.emit()

    # ---- finish ------------------------------------------------------------------------------
    def accept(self) -> None:
        try:
            folder = create_project(self.answers(), Path(self.folder_edit.text().strip() or "."))
        except WizardError as exc:
            self.error_label.setText(str(exc))
            return
        super().accept()
        self.created.emit(folder)
