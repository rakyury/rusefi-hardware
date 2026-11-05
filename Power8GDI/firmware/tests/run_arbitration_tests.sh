#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
${CXX:-g++} -std=c++17 -O2 -Wall -Wextra -Werror -pedantic ${SANITIZE:--fsanitize=undefined} \
  arbitration/intervention_accumulator.cpp arbitration/task_cycle.cpp arbitration/ignition_arbiter.cpp \
  tests/test_arbitration.cpp -o "$build/test_arbitration"
"$build/test_arbitration"
