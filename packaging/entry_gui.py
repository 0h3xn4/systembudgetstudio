"""Entry point of the GUI executable (PyInstaller)."""

import sys

from budget_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
