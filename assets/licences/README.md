# Third-party licence texts

`LGPL-3.0.txt` and `GPL-3.0.txt` are the licence texts of the Qt libraries and the PySide6 / shiboken6
bindings (used under the GNU LGPL v3, which refers to the GPL v3 text). Qt and PySide6 are shipped
unmodified as separate shared libraries inside the bundle, so a user can replace them with another
build of the same version. The source of Qt and Qt for Python is available from The Qt Company
(https://www.qt.io) and the Qt Project (https://code.qt.io); this tool never contacts those sites.

The IBM Plex fonts are under the SIL Open Font License 1.1 (`../fonts/OFL-IBM-Plex.txt`).
The licence texts of the Python packages are collected into `licences/` next to the program
at build time (`packaging/licence_check.py --collect`).
