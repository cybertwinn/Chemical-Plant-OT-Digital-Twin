#!/bin/bash
set -e

cd ~/OTwin-MeOH-vessel/src
source ~/minicps/minicps-env/bin/activate

python init.py

# Use 'sudo -E' AND the exact python from the venv:
sudo -E $(which python) run.py

