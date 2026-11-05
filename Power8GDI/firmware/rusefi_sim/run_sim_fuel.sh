#!/usr/bin/env bash
# Build the rusEFI simulator with the Power8GDI glue and check the fuel /
# cylinder-cut arbitration. Usage (inside WSL): bash run_sim_fuel.sh [path-to-rusefi] [seconds]
#
# Every check runs with 6 cylinders (Power6GDI, firing order 1-5-3-6-2-4) and
# with the simulator's default 4, so the cylinder count stays a parameter.
#
# Runs scenario `fuelcut` (knock fuel trim, soft window, hard limit fuel cut,
# launch fuel cut, table) twice:
#   shadow  arbiter == rusEFI: per-cylinder multipliers (stock trim x knock trim),
#           every cylinder cut exactly when rusEFI cuts injection, lambda target
#   apply   the arbiter drives injectionMass[]: cut cylinders get mass 0, the
#           others the arbiter ratio; a progressive soft rev-limit cylinder cut
#           (Power8GDI strategy) cuts the requested share, every cylinder in turn
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
rusefi=${1:-$HOME/rusefi}
seconds=${2:-12}

make -C "$rusefi/simulator" -j"$(nproc)" BOARD_DIR="$here" >/tmp/p8_sim_build.log 2>&1 || {
  grep -E "error|\*\*\*" /tmp/p8_sim_build.log | head -20 || true
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

run() {  # run <apply 0|1> <cylinders 4|6>
  P8_SIM_APPLY=$1 P8_SIM_CYLINDERS=$2 P8_SIM_SCENARIO=fuelcut timeout $((seconds + 30)) ./build/rusefi_simulator "$seconds" 2>&1 |
    grep '^P8FUEL cycles=' | tail -1
}

for spec in 6:0 6:1 4:0 4:1; do
  cylinders=${spec%%:*}
  apply=${spec#*:}
  last=$(run "$apply" "$cylinders")
  echo "[cylinders=$cylinders apply=$apply fuelcut] $last"
  [[ -n "$last" ]] || fail "no report"
  [[ $(field cylinders "$last") == "$cylinders" ]] || fail "cylinder count not applied"
  [[ $(field cycles "$last") -ge 1500 ]] || fail "run shorter than the five scenario phases"
  [[ $(field mismatches "$last") == 0 ]] || fail "arbiter != rusEFI"
  [[ $(field massChecks "$last") -gt 0 ]] || fail "injection mass never checked"
  [[ $(field massErrors "$last") == 0 ]] || fail "rusEFI injectionMass != arbiter result"
  [[ $(field knockFuelCycles "$last") -gt 0 ]] || fail "knock fuel trim not seen"
  reasons=$(field cutReasons "$last")
  # ClearReason bits: 3 = HardLimit, 9 = LaunchCut
  (( (reasons & 0x208) == 0x208 )) || fail "hard limit and launch fuel cuts not both seen: $reasons"
  [[ $(field allCutCycles "$last") == $(field rusefiCutCycles "$last") ]] || fail "full cut cycles differ"

  if [[ $apply == 1 ]]; then
    [[ $(field zeroMassCycles "$last") -gt 0 ]] || fail "full cut never gave zero mass on every cylinder"
    [[ $(field softCycles "$last") -gt 0 ]] || fail "soft cylinder cut never active"
    awk -v a="$(field softCuts "$last")" -v e="$(field softExpected "$last")" \
      'BEGIN { d = a - e; if (d < 0) d = -d; exit !(d <= 1) }' || fail "soft cut share != request"
    [[ $(field softPerCylMin "$last") -gt 0 ]] || fail "a cylinder was never cut in the soft window"
    (( $(field softPerCylMax "$last") - $(field softPerCylMin "$last") <= 1 )) || fail "soft cut not shared evenly"
  else
    [[ $(field softCycles "$last") == 0 ]] || fail "shadow mode requested a cylinder cut"
  fi
done
echo "Power8GDI fuel arbitration in rusEFI simulator: PASS"
