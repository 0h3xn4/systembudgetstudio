# PyInstaller spec: one-folder build (portable zip / installer payload). Run from the repo root.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "src" / "budget_gui" / "app.py")],
    pathex=[str(root / "src")],
    datas=[(str(root / "assets"), "budget_core/assets")] + collect_data_files("pint"),
    hiddenimports=["pint", "ruamel.yaml", "openpyxl", "reportlab.pdfbase._fontdata"],
    # ssl, http and urllib cannot be excluded: ReportLab imports them (and never uses them for
    # network access, see DECISIONS D-043). The Qt network module is not needed.
    excludes=["PySide6.QtNetwork", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="system-budget-studio",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="system-budget-studio")
