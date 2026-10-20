#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash tests/run_host_tests.sh
bash tests/run_map4d_wire_tests.sh
bash tests/run_dual_hpfp_tests.sh
