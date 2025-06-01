#!/bin/bash

# Activate the virtual environment
source /home/adrian/repo/ha-bambulab/custom_components/bambu_lab/pybambu/venv/bin/activate
pip install -r /home/adrian/repo/ha-bambulab/custom_components/bambu_lab/pybambu/tests/requirements.txt

# Change to the parent directory of pybambu
cd /home/adrian/repo/ha-bambulab/custom_components/bambu_lab

# Run the tests with PYTHONPATH set
PYTHONPATH=. python3 -m unittest pybambu.tests.test_models -v

# Deactivate the virtual environment
deactivate