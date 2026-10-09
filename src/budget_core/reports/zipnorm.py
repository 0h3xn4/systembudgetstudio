"""Rewrite a ZIP (XLSX/DOCX) with fixed timestamps and stable order, for byte-identical output."""

from __future__ import annotations

import io
import zipfile

FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def normalise_zip(data: bytes) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dst:
        for name in sorted(src.namelist()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            dst.writestr(info, src.read(name))
    return out.getvalue()
