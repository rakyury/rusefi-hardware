#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
c++ -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude tests/test_map4d_blob.cpp -o /tmp/power8gdi_map4d_blob_test
/tmp/power8gdi_map4d_blob_test
echo '4D blob C++ host tests: PASS'
