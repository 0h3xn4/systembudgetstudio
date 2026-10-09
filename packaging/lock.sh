#!/usr/bin/env bash
# Regenerate hashed lock files (runtime and dev) with uv. Run on a connected machine.
set -euo pipefail
cd "$(dirname "$0")/.."
uv pip compile pyproject.toml --universal --python-version 3.11 --generate-hashes \
  --no-header -o requirements.lock
uv pip compile pyproject.toml --extra dev --universal --python-version 3.11 --generate-hashes \
  --no-header -o requirements-dev.lock
