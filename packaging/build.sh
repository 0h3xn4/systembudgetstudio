#!/usr/bin/env bash
# Build the portable one-folder bundle, its CycloneDX SBOM and its licence report.
# Needs the dev extra (pyinstaller, cyclonedx-bom, pip-licenses). The SBOM and the licence report
# describe what is shipped, so they are made from a runtime-only environment installed from the
# hashed lock file, never from the development environment.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
BUNDLE=dist/system-budget-studio

"$PY" -m PyInstaller --noconfirm --distpath dist --workpath build packaging/system_budget_studio.spec

RT="$(mktemp -d)"
trap 'rm -rf "$RT"' EXIT
"$PY" -m venv --without-pip "$RT/venv"
if [ -x "$RT/venv/Scripts/python.exe" ]; then RTPY="$RT/venv/Scripts/python.exe"; else RTPY="$RT/venv/bin/python"; fi
"$PY" -m pip --python "$RTPY" install --quiet --require-hashes -r requirements.lock
cyclonedx-py environment --of JSON --pyproject pyproject.toml -o dist/sbom.cdx.json "$RTPY"
pip-licenses --python "$RTPY" --format=markdown --output-file dist/licences.md

# The licence material travels with the program: texts, the licence report and the SBOM.
"$PY" packaging/licence_check.py --collect "$BUNDLE/licences"
cp dist/licences.md dist/sbom.cdx.json "$BUNDLE/"
"$PY" packaging/check_bundle.py "$BUNDLE"
