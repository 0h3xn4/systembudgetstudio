"""Entry point of the command-line executable `budget` (PyInstaller)."""

import sys

from budget_cli.main import main

if __name__ == "__main__":
    sys.exit(main())
