#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash tests/run_host_tests.sh
bash tests/run_map4d_wire_tests.sh
bash tests/run_dual_hpfp_tests.sh
bash tests/run_gdi_safety_tests.sh
"${PYTHON:-python3}" tests/run_fuel_gdi6_tests.py
"${PYTHON:-python3}" tests/run_racing_dash_tests.py
