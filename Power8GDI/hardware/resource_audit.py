"""Conservative MCU signal budget audit for Power8GDI Rev A.

Checks *logical* signal ownership and provisional pin-name collisions.
Does NOT replace STM32CubeMX AF/ADC/DMA allocation or KiCad ERC/DRC.
Release approval is withheld when any requirement lacks an assignment.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINOUT = HERE.parent / "pinout" / "power8gdi_revA_pinout.csv"
RESOURCE = HERE / "mcu_gpio_draft.csv"

# Internal logical signals on the MCU side; some outputs MAY eventually be
# implemented via a suitable external driver instead of one MCU pin per channel.
REQUIRED = {
    "Timed GDI commands": [*(f"DI{i}" for i in range(1, 9)),
                            *(f"HPFP{i}" for i in range(1, 3))],
    "Ignition & optional PI": [*(f"IGN{i}" for i in range(1, 9)),
                               *(f"PI{i}" for i in range(1, 9))],
    "PT2001 controls": [f"PT{chip}_{mode}" for chip in "AB"
                         for mode in ("CS", "RESET", "DRVEN", "FLAG")],
    "Motor bridges": [f"{act}_{cmd}" for act in ("DBW", "EWG")
                      for cmd in ("PWM", "DIR", "DISABLE")],
    "Valve control": [*(f"VVT{i}" for i in range(1, 5)),
                      *(f"AUX_PWM{i}" for i in range(1, 9)),
                      *(f"LS_AUX{i}" for i in range(1, 5))],
    "Crank & cams": ["CRANK", *(f"CAM{i}" for i in range(1, 5))],
    "Knock serial controls": ["KNOCK_CS_N", "KNOCK_INT_HOLD"],
    "SENT input capture": [f"SENT{i}" for i in range(1, 5)],
    "LIN": [f"LIN{i}_{d}" for i in range(1, 3) for d in ("TX", "RX")],
    "CAN": [f"CAN{i}_{d}" for i in range(1, 3) for d in ("TX", "RX")],
    "GDI SPI2": [f"GDI_SPI2_{d}" for d in ("SCK", "MISO", "MOSI")],
}


class ResourceConflict(ValueError):
    """Fatal contradiction in provisional resource file."""


def read_rows(path: Path = RESOURCE) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or set(("function", "stm32_pin", "mcu_resource", "status", "notes")) - set(rows[0]):
        raise ResourceConflict("Malformed GPIO allocation sheet")
    return rows


def audit(rows: list[dict[str, str]]) -> dict:
    by_function = {}
    physical = {}
    for row in rows:
        name = row["function"].strip()
        pin = row["stm32_pin"].strip()
        if not name or name in by_function:
            raise ResourceConflict(f"Duplicate or empty function: {name!r}")
        by_function[name] = row
        if pin != "UNASSIGNED":
            if not pin or not (pin.startswith("P") and len(pin) in (3, 4)):
                raise ResourceConflict(f"Invalid pin token {name}: {pin!r}")
            if pin in physical:
                raise ResourceConflict(f"MCU pin {pin}: {name} overlaps {physical[pin]}")
            physical[pin] = name

    groups = {}
    gaps = []
    for label, funcs in REQUIRED.items():
        assigned = [name for name in funcs
                    if name in by_function and by_function[name]["stm32_pin"] != "UNASSIGNED"]
        missing = [name for name in funcs if name not in assigned]
        groups[label] = {"assigned": len(assigned), "required": len(funcs), "missing": missing}
        gaps.extend(missing)
    all_required = set(sum(REQUIRED.values(), []))
    return {
        "allocation_complete": not gaps,
        "complete": False,
        "release_eligible": False,
        "revision": "Rev A preliminary / NO KiCad AF/DRC qualification",
        "mcu_candidate": "STM32F767IIT6, LQFP176 - not yet finalized",
        "total_mcu_functions": len(rows),
        "assigned_gpio": len(physical),
        "required_functions": len(all_required),
        "unassigned_required": gaps,
        "groups": groups,
        "known_hardware_conflicts": [
            "STM32 PC6 TIM3_CH1 and PC8 TIM3_CH3 share timer frequency",
            "PA15 provisional PTB_CS overlaps Hellen H_SPI3_CS/CAN termination pattern",
            "DI6/DI7/DI8 reuse Power4GDI LS6 HPFP / LS7 DRVEN / LS8 RESET",
            "Knock1/2 use TPIC8101 multiplexed SPI; timing and DSP configuration unqualified",
            "24 LS outputs require high-current/timing/PWM-specific hardware; TLE9104 count alone insufficient",
            "WBO1/2 6-pin connectors are not analog sensors: require qualified wideband analog front-end",
        ],
    }


def validate_connector_groups() -> None:
    with PINOUT.open(newline="", encoding="utf-8") as stream:
        nets = {row["net"] for row in csv.DictReader(stream)}
    for i in range(1, 9):
        for signal in (f"DI{i}_HIGH", f"DI{i}_LOW", f"PI{i}", f"IGN{i}", f"AUX_PWM{i}"):
            if signal not in nets:
                raise ResourceConflict(f"Missing connector signal {signal}")
    for x in ("WBO1_CONTACT1", "WBO2_CONTACT1", "HPFP1_HIGH", "HPFP2_HIGH",
              "SENT1", "SENT4", "LIN1_BUS", "LIN2_BUS"):
        if x not in nets:
            raise ResourceConflict(f"Missing connector signal {x}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="Return nonzero unless GPIO allocation and electrical qualification are complete")
    ap.add_argument("--json", action="store_true", help="Produce full machine-readable resource gap report")
    args = ap.parse_args()
    validate_connector_groups()
    report = audit(read_rows())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for group, stats in report["groups"].items():
            print(f"{group}: {stats['assigned']}/{stats['required']} assigned")
        print("Qualification blocked; allocation complete:",
              report["allocation_complete"], len(report["unassigned_required"]), "required functions unresolved")
    return 0 if not args.strict or report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
