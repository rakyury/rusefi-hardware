#!/usr/bin/env bash
# Build the rusEFI simulator with the Power8GDI glue and check the arbitration.
# Usage (inside WSL): bash run_sim_arbitration.sh [path-to-rusefi] [seconds]
#
# Runs:
#   shadow/none    arbiter == rusEFI, nothing injected
#   shadow/knock   arbiter == rusEFI with knock retard, while cranking and on the table
#   shadow/owners  arbiter == rusEFI with knock + limiter retard for every angle owner
#   apply/owners   arbiter drives the angle; rusEFI's final angle == arbiter angle;
#                  differs from rusEFI exactly in the non-table cycles (limiter
#                  retard dropped there by the Power8GDI default, knock kept)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
rusefi=${1:-$HOME/rusefi}
seconds=${2:-12}

make -C "$rusefi/simulator" -j"$(nproc)" BOARD_DIR="$here" >/tmp/p8_sim_build.log 2>&1 || {
  grep -E "error" /tmp/p8_sim_build.log | head -20
  echo "FAIL: build"
  exit 1
}
cd "$rusefi/simulator"

field() {  # field <name> <line>
  sed -nE "s/.* $1=([^ ]+).*/\1/p" <<<"$2"
}

fail() {
  echo "FAIL: $*"
  exit 1
}

run() {  # run <apply 0|1> <scenario>
  P8_SIM_APPLY=$1 P8_SIM_SCENARIO=$2 timeout $((seconds + 30)) ./build/rusefi_simulator "$seconds" 2>&1 |
    grep '^P8SHADOW cycles=' | tail -1
}

for spec in 0:none 0:knock 0:owners 1:owners; do
  apply=${spec%%:*}
  scenario=${spec#*:}
  last=$(run "$apply" "$scenario")
  echo "[apply=$apply $scenario] $last"
  [[ -n "$last" ]] || fail "no report"
  [[ $(field mismatches "$last") == 0 ]] || fail "mismatches"

  owners=$(sed -nE 's/.*owners\[T,O,I,A,L,C\]=([0-9,]+).*/\1/p' <<<"$last")
  IFS=, read -r t o i a l c <<<"$owners"

  case $scenario in
    knock)
      [[ $(field knockOwners "$last") == 0x21 ]] || fail "knock not seen while cranking and on the table"
      ;;
    owners)
      for n in "$t" "$o" "$i" "$a" "$l" "$c"; do
        [[ $n -gt 0 ]] || fail "an angle owner was not reached: $owners"
      done
      [[ $(field knockOwners "$last") == 0x3f ]] || fail "knock retard not seen for every owner"
      [[ $(field limiterOwners "$last") == 0x3f ]] || fail "limiter retard not seen for every owner"
      ;;
  esac

  if [[ $apply == 1 ]]; then
    [[ $(field appliedChecks "$last") -gt 0 ]] || fail "final angle never checked"
    [[ $(field applyErrors "$last") == 0 ]] || fail "rusEFI final angle != arbiter angle"
    [[ $(field differentCycles "$last") == $((o + i + a + l + c)) ]] ||
      fail "arbiter differs from rusEFI outside the non-table owners"
  else
    [[ $(field differentCycles "$last") == 0 ]] || fail "differentCycles in shadow mode"
  fi
done
echo "Power8GDI arbitration in rusEFI simulator: PASS"
