# PyInstaller spec: one-folder build (portable zip / installer payload). Run from the repo root.
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "src" / "budget_gui" / "app.py")],
    pathex=[str(root / "src")],
    datas=[(str(root / "assets"), "budget_gui/assets")],
    excludes=["PySide6.QtNetwork", "tkinter", "ssl", "_ssl"],
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
