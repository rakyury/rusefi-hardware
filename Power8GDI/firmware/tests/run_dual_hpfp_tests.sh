#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
${CXX:-g++} -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -fsanitize=undefined \
  dual_hpfp/dual_hpfp_supervisor.cpp tests/test_dual_hpfp_supervisor.cpp \
  -o "$build/test_dual_hpfp"
"$build/test_dual_hpfp"
