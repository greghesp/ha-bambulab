#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies
pip install -r "$SCRIPT_DIR/tests/requirements.txt"

# Change to repository root
cd "$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

# Run tests.
# NOTE: Preload the stdlib 'select' module before importing anything from
# Home Assistant's integration tree to avoid shadowing by platform files like
# custom_components/bambu_lab/select.py.
python3 - <<'PY'
import os
import sys
import unittest

import select  # noqa: F401

repo_root = os.getcwd()
sys.path.insert(0, os.path.join(repo_root, "custom_components", "bambu_lab"))

suite = unittest.defaultTestLoader.loadTestsFromNames(
	[
		"pybambu.tests.test_models",
		"pybambu.tests.test_error_lookup",
		"pybambu.tests.test_utils",
	]
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
PY

# Deactivate virtual environment
deactivate