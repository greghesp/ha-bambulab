#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r tests/requirements.txt

# Change to the parent directory of pybambu
cd /home/adrian/repo/ha-bambulab/custom_components/bambu_lab/pybambu

# Run tests with PYTHONPATH set
PYTHONPATH=/home/adrian/repo/ha-bambulab/custom_components/bambu_lab/pybambu python3 -m unittest tests/test_models.py -v

# Deactivate virtual environment
deactivate