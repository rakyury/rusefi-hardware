# Local logic power copper checkpoint — 2026-10-23

This is **partial local routing**, not a functional or fabrication-ready board.
The module places 30 buck components and adds 106 B.Cu segments plus 22 GND
through vias on the reviewed 1236-component input snapshot. D5200/D5201 remain
owned by the generic input-protection placement stage. Their old positions must
not be treated as accepted by this module.

## Integration contract

Requires the shared `voltage_domains.py` and `audit_gdi_voltage_domains.py`.
Call `voltage_domains.configure(actual_core_net)` before
`place_and_route(board, fps, nets, fixed_references, region=(5,5,151,55))`.
Run **before** packing other new modules. Only imported donor footprints and
fixed MCU/IGN/connectors belong in `fixed_references`; unplaced modules must
not be obstacles. Add returned `placed_references` to the generic packer's
placed set, and treat all added tracks/vias as subsequent packing obstacles.

The module refuses existing local buck copper or tracks touching owned pads.
It restores original coordinates, angles and front/back layers when a cell
does not fit. It preserves all foreign footprints and existing copper. The
standalone CLI refuses to overwrite its input. Both the placement search and
local routing honor the exact netlist-derived PT2001 switching domains, not
only nets containing VBOOST. Via checks cover all four copper layers and
same-net drilled-hole spacing. Track collision checks use actual segment
distance rather than the bounding box of a diagonal segment.

## Reproduced checks

Input PCB SHA256:
`1f6d8918f18fa8f4c4a6bf7166e4b0b4e5ced781cb43eee97ad452f0b7ffd740`.
Core netlist SHA256:
`d7fb0ddc652c735b1617ddce309dcb4ca93b4729c80044e7e9be3e5e50e74ae7`.
Pinned runtime:
`kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.

Structural checks preserved all 1204 foreign footprints, all 2538 original
copper items and every pad net assignment. Routed-input rejection and
impossible-region restoration mutation checks pass. New track widths are at
least 0.2 mm; vias are 0.6 mm diameter / 0.3 mm drill. Those sizes are geometry
constraints, not a current or thermal qualification.

The native KiCad DRC comparison uses copies containing the donor, fixed MCU/
connectors and logic-power components. Other unplaced new modules are absent.
Both fixtures use identical project settings plus the audited 60-net HV rule,
zone refill and `--all-track-errors`. [Machine-readable evidence](logic_power_local_review.json)
contains hashes, counts, local findings and unfinished connectivity.

| Native pre-pack fixture result | Before | After |
|---|---:|---:|
| Unconnected items | 289 | 226 |
| Clearance findings | 505 | 500 |
| Track-width findings (existing donor) | 199 | 199 |
| Hole-to-hole findings | 0 | 0 |
| Total violations, including library/silk/warnings | 960 | 996 |

For the **30 moved buck references and 128 added copper items**, there are no
native clearance, short, width or drilled-hole errors in this fixture. Two
intentional global breakout ends remain dangling. Dense reference text produces
additional silk findings; total DRC is consequently not improved or clean.
One D5200 NC pad at (25.625,14.055) remains only 0.31 mm from a PTA_H1 donor via;
the generic packer must relocate D5200 under the new 0.6 mm rule.

## What is actually connected and what remains

Local copper connects the LM76003 PVIN input capacitors, HF return, SW pin bus,
inductor and output-capacitor rows; BOOT capacitor loop, VCC and BIAS local
bypasses, FB divider/Cff, AGND-to-EP and selected PGND returns are implemented.
TPS62130A local SW/inductor/Cout, separate VOS trace, PVIN and AVIN bypasses,
FSW strap, FB divider, SS, AGND/PGND/DEF-to-EP and EN breakout are implemented.
Twenty-two vias include five accepted LM EP vias, four TPS EP vias and thirteen
capacitor-ground stitches. Three proposed LM EP vias were rejected because of
PTA_VBOOST copper on another layer.

**Required remaining work:** LM output-to-feedback/BIAS supply connection and
quiet SS-cap ground return are blocked by existing PT current-sense/L3 copper
on B.Cu. Both paths are rejected whole; no silent net swap or clipped route is
inserted. LM EN divider/feed, PG connection, remaining MODE/NC/ground pins,
TPS upper-divider supply, PG, bleed resistor and divider ground, AVIN-to-PVIN
feed, inter-buck supply/PG, D5200/D5201 feeds, global rail distribution and
silkscreen placement still need explicit routing. The full local unconnected
list is recorded in the JSON; “106 segments” is not electrical completion.

## Repeat

Run these Python/CLI entry points in the pinned KiCad container, using paths
inside the mounted worktree:

```
python3 route_logic_power_local.py --input INPUT.kicad_pcb --output ROUTED.kicad_pcb --report routing.json --netlist core.net
python3 check_logic_power_local.py --input INPUT.kicad_pcb --routed ROUTED.kicad_pcb --netlist core.net --report routing.json --output checks.json
python3 prepare_logic_power_fixture.py --source INPUT.kicad_pcb --output BEFORE.kicad_pcb --project ORIGINAL.kicad_pro --netlist core.net
python3 prepare_logic_power_fixture.py --source ROUTED.kicad_pcb --output AFTER.kicad_pcb --project ORIGINAL.kicad_pro --netlist core.net
kicad-cli pcb drc --all-track-errors --format json --output before_drc.json BEFORE.kicad_pcb
kicad-cli pcb drc --all-track-errors --format json --output after_drc.json AFTER.kicad_pcb
```

Use a distinct process per fixture. Source boards and upstream designs remain
untouched. The fixture helper copies project rules before loading/refilling and
after saving, so KiCad cannot silently replace the comparison with defaults.

## Primary layout requirements and limits

[TI LM76003-Q1 datasheet](https://www.ti.com/lit/ds/symlink/lm76003-q1.pdf),
sections 10.1–10.3, drives the short PVIN/PGND hot loop, local VCC/BIAS bypass,
quiet feedback and exposed-pad/ground-plane connections.
[TI TPS62130A-Q1 datasheet](https://www.ti.com/lit/ds/symlink/tps62130a-q1.pdf),
section 12, requires the common AGND/PGND/EP return and separate output sensing.
The available donor geometry constrains the EP vias and surrounds parts of the
cells with GDI current-sense and switching copper. Native DRC cannot establish
acceptable feedback noise, thermal impedance, via-in-pad assembly suitability,
EMC, transient behavior or rail stability. No such qualification is claimed.
