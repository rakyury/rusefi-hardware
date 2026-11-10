#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p /tmp/power8gdi_tests
c++ -std=c++17 -O2 -Wall -Wextra -Werror -Iinclude \
  tests/test_map4d.cpp -o /tmp/power8gdi_tests/test_map4d
/tmp/power8gdi_tests/test_map4d
printf 'map4d host tests: passed\n'
