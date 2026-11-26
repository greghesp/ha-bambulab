#!/bin/bash
# Convenience wrapper for local development. CI runs the same suite via
# .github/workflows/tests.yml — this script exists so contributors can run
# it the same way without pushing.
#
#   tests/run_tests.sh           # newest Home Assistant, in .venv
#   tests/run_tests.sh minimum   # the minimum in hacs.json, in .venv-minimum (needs uv)
set -e

# Get the directory where this script is located (repo_root/tests)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

if [ "$1" = "minimum" ]; then
    eval "$(python3 scripts/ha_min_version.py ci-env minimum)"
    uv venv --quiet --allow-existing --python "$python" .venv-minimum
    source .venv-minimum/bin/activate
    uv pip install --quiet -r tests/requirements_ha.txt "homeassistant==$version"
    python -m pytest tests -v
    exit
fi

python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install --quiet -r tests/requirements_ha.txt
python3 -m pytest tests -v
