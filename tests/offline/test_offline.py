"""No networking: sockets blocked at runtime, networking modules must not be imported.

Each scenario runs in a fresh interpreter so import state is clean.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

FORBIDDEN = (
    "http.client",
    "urllib.request",
    "ssl",
    "requests",
    "urllib3",
    "ftplib",
    "smtplib",
    "xmlrpc.client",
    "aiohttp",
    "httpx",
    "PySide6.QtNetwork",
)

PRELUDE = """
import socket, sys
def _blocked(*a, **k):
    raise AssertionError("network access attempted")
socket.socket.connect = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
"""

CHECK = f"""
bad = [m for m in {FORBIDDEN!r} if m in sys.modules]
assert not bad, f"networking modules imported: {{bad}}"
"""


def _run(body: str, allowed: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    check = CHECK.replace(
        "for m in " + repr(FORBIDDEN),
        "for m in " + repr(tuple(m for m in FORBIDDEN if m not in allowed)),
    )
    code = PRELUDE + textwrap.dedent(body) + check
    env = {"QT_QPA_PLATFORM": "offscreen", "PATH": ""}
    return subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, env=env, check=False
    )


def test_core_and_cli_do_not_import_network_modules() -> None:
    r = _run("import budget_core, budget_cli.main as m; m.main([])")
    assert r.returncode == 0, r.stderr


def test_loader_validation_and_unit_parsing_do_not_use_the_network() -> None:
    r = _run("""
        import tempfile, pathlib
        from budget_core.examples import export_examples
        from budget_core.io.project_loader import load_project
        from budget_core.units.quantity import parse_quantity
        assert parse_quantity("2.2 GHz", "freq_hz") == 2.2e9  # forces pint
        with tempfile.TemporaryDirectory() as d:
            export_examples(pathlib.Path(d))
            assert load_project(pathlib.Path(d) / "cubesat_3u").project is not None
    """)
    assert r.returncode == 0, r.stderr


def test_gui_starts_offline() -> None:
    r = _run("""
        import sys
        from budget_gui.app import create_app
        from budget_gui.main_window import MainWindow
        app = create_app(["x"]); w = MainWindow(); w.show(); app.processEvents()
    """)
    assert r.returncode == 0, r.stderr


def test_guard_detects_network_use() -> None:
    """Negative test: the harness must fail when a socket is opened or a module imported."""
    r = _run("import socket; socket.create_connection(('127.0.0.1', 9))")
    assert r.returncode != 0
    r = _run("import http.client")
    assert r.returncode != 0


# ReportLab imports these at module level only to fetch images from URLs, which this tool never
# does (it restricts ReportLab to local files). Only the PDF renderer may bring them in (D-043).
REPORTLAB_IMPORTS = ("urllib.request", "http.client", "ssl")


def test_xlsx_and_json_report_path_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        project = {str(tmp_path / "cubesat_3u")!r}
        code = main(["run", project, "--report", "xlsx", "--report", "json",
                     "--report", "csv", "--out", {str(tmp_path / "out")!r}])
        assert code == 0
    """)
    assert r.returncode == 0, r.stderr


def test_pdf_path_imports_only_the_allowed_reportlab_modules_and_never_uses_the_network(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    r = _run(
        f"""
        import pathlib, urllib.request
        called = []
        orig = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: called.append(a) or orig(*a, **k)
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        code = main(["run", {str(tmp_path / "cubesat_3u")!r}, "--report", "pdf",
                     "--out", {str(tmp_path / "out")!r}])
        assert code == 0 and not called
        from reportlab import rl_config
        assert set(rl_config.trustedSchemes) == {{"file", "data"}}
        assert rl_config.trustedHosts == ["localhost.invalid"]
    """,
        allowed=REPORTLAB_IMPORTS,
    )
    assert r.returncode == 0, r.stderr


def test_reportlab_refuses_remote_resources() -> None:
    r = _run(
        """
        import urllib.request
        called = []
        urllib.request.urlopen = lambda *a, **k: called.append(a)
        import budget_core.reports.pdf
        from reportlab.lib.utils import open_for_read
        try:
            open_for_read("https://example.com/logo.png")
        except OSError:
            pass
        else:
            raise SystemExit("remote resource was opened")
        assert not called, "a network fetch was attempted"
    """,
        allowed=REPORTLAB_IMPORTS,
    )
    assert r.returncode == 0, r.stderr
