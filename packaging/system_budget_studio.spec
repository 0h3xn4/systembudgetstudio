# PyInstaller spec: one-folder build (portable zip / installer payload). Run from the repo root.
# The folder holds two executables that share one set of libraries: the windowed
# `system-budget-studio` and the console tool `budget` (batch runs, scripts).
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "entry_gui.py"), str(root / "packaging" / "entry_cli.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(root / "assets"), "budget_core/assets"),
        (str(root / "src" / "budget_core" / "guide" / "chapters"), "budget_core/guide/chapters"),
    ]
    + collect_data_files("pint")
    # python-docx reads its templates through "<package>/parts/../templates"; the .py files are
    # included so that the parts folder exists in the bundle (the path has to resolve).
    + collect_data_files("docx", include_py_files=True),
    hiddenimports=["pint", "ruamel.yaml", "openpyxl", "reportlab.pdfbase._fontdata", "sgp4.vallado_cpp", "docx", "PIL"],
    # ssl, http and urllib cannot be excluded: ReportLab imports them (and never uses them for
    # network access, see DECISIONS D-043). The Qt network module is not needed.
    excludes=["PySide6.QtNetwork", "tkinter"],
)
pyz = PYZ(a.pure)


def scripts(keep):
    """The bootstrap scripts plus the one entry script of an executable."""
    own = {"entry_gui", "entry_cli"}
    return [s for s in a.scripts if s[0] not in own or s[0] == keep]


gui = EXE(
    pyz,
    scripts("entry_gui"),
    [],
    exclude_binaries=True,
    name="system-budget-studio",
    console=False,
)
cli = EXE(
    pyz,
    scripts("entry_cli"),
    [],
    exclude_binaries=True,
    name="budget",
    console=True,
)
coll = COLLECT(gui, cli, a.binaries, a.datas, name="system-budget-studio")
