#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies
pip install -r "$SCRIPT_DIR/tests/requirements.txt"

# Change to the parent directory of pybambu (bambu_lab directory)
cd "$(dirname "$SCRIPT_DIR")"

# Run tests with PYTHONPATH set to include the parent directory
PYTHONPATH="$(pwd)" python3 -m unittest pybambu.tests.test_models -v

# Deactivate virtual environment
deactivate