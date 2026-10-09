"""Location of the bundled assets (IBM Plex fonts and licence). No network, no downloads."""

from __future__ import annotations

from pathlib import Path


def assets_dir() -> Path:
    """Installed wheel, source checkout or PyInstaller bundle, in that order."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "assets", here.parent.parent / "assets"):
        if (candidate / "fonts").is_dir():
            return candidate
    raise FileNotFoundError("Bundled assets folder not found; the installation is incomplete.")


def font_path(name: str) -> Path:
    return assets_dir() / "fonts" / name
