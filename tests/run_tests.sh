#!/bin/bash
# Convenience wrapper for local development. CI runs the same suite via
# .github/workflows/tests.yml — this script exists so contributors can run
# it the same way without pushing.
set -e

# Get the directory where this script is located (repo_root/tests)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

python3 -m pip install --quiet -r tests/requirements.txt
python3 -m pytest tests/pybambu -v
