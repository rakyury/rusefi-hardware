#!/usr/bin/env bash
# Build the rusEFI simulator with the Power8GDI glue and run the shadow check.
# Usage (inside WSL): bash run_sim_shadow.sh [path-to-rusefi] [seconds]
# Fails unless the final report has mismatches=0 and, in the knock scenario,
# knockCycles>0 with knock seen while cranking (owner bit 5) and on the table (bit 0).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
rusefi=${1:-$HOME/rusefi}
seconds=${2:-15}
make -C "$rusefi/simulator" -j"$(nproc)" BOARD_DIR="$here" >/dev/null
cd "$rusefi/simulator"
for scenario in none knock; do
  last=$(P8_SIM_SCENARIO=$scenario timeout $((seconds + 30)) ./build/rusefi_simulator "$seconds" 2>&1 | grep '^P8SHADOW cycles=' | tail -1)
  echo "[$scenario] $last"
  [[ -n "$last" ]] || { echo "FAIL: no report"; exit 1; }
  [[ "$last" == *" mismatches=0 "* ]] || { echo "FAIL: mismatches"; exit 1; }
  if [[ $scenario == knock ]]; then
    [[ "$last" != *" knockCycles=0 "* ]] || { echo "FAIL: knock not exercised"; exit 1; }
    [[ "$last" == *"knockOwners=0x21 "* ]] || { echo "FAIL: knock not seen while cranking and on the table"; exit 1; }
  fi
done
echo "Power8GDI shadow arbitration in rusEFI simulator: PASS"
