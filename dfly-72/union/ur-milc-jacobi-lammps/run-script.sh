#!/usr/bin/bash
# 4-Application Stress Testing Suite Wrapper
# Calls the Python implementation for better maintainability

expfolder="$PWD"
export CONFIGS_PATH="$PATH_TO_SCRIPT_DIR/conf"
# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/run_stress_tests.py"
