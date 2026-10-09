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


def _run(body: str) -> subprocess.CompletedProcess[str]:
    code = PRELUDE + textwrap.dedent(body) + CHECK
    env = {"QT_QPA_PLATFORM": "offscreen", "PATH": ""}
    return subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, env=env, check=False
    )


def test_core_and_cli_do_not_import_network_modules() -> None:
    r = _run("import budget_core, budget_cli.main as m; m.main([])")
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
