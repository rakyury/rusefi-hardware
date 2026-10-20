#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
c++ -std=c++17 -Wall -Wextra -Werror -O2 -I dual_gdi tests/test_dual_pt2001_safety.cpp \
    dual_gdi/dual_pt2001_safety.cpp -o /tmp/power8gdi_dual_gdi_host
/tmp/power8gdi_dual_gdi_host
echo 'dual PT2001 safety host tests: PASS'
