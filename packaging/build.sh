#!/usr/bin/env bash
# Build the portable one-folder bundle and a CycloneDX SBOM + licence report (dev extra required).
set -euo pipefail
cd "$(dirname "$0")/.."
pyinstaller --noconfirm --distpath dist --workpath build packaging/system_budget_studio.spec
cyclonedx-py environment --of JSON -o dist/sbom.cdx.json
pip-licenses --format=markdown --output-file dist/licences.md
