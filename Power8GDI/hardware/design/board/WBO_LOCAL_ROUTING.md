# WBO local placement and routing checkpoint

`route_wbo_local.place_and_route(board, fps, nets, fixed_references, regions)`
is called after fixed donor/connector/MCU/ignition placement and before generic
packing. Exclude returned `placed_references` from subsequent generic packing.
`regions` is an optional mapping `{1: (153,52,197,142), 2: (198,52,242,142)}`.
Both board sides are allowed. Donor footprints and copper must remain fixed.

Dependencies: integration `audit_gdi_voltage_domains.py` (998f104),
`voltage_domains.py` (9efc0cd, including battery aliases), current WBO manifest/reference and KiCad9 pcbnew.
The caller should configure `voltage_domains` from its actual `core.net` first.
Standalone use configures the adjacent core.net. Every discovered PT-domain
node is independently checked against actual footprint pad nets before work.

The module requires all174 current WBO parts with matching values/pad nets.
It seeds the pinned Hellen layout at1.5 scale, places actual enlarged bodies,
and makes limited side/position adjustments around retained donor obstacles.
New LT3042/reset/inhibit/power parts have explicit placement seeds. The REF/SET/
LDO cluster has a second placement pass, and actual pin-to-pin decoupling rail
branches are routed before general signals. It does
not copy source copper. Existing power-zone outlines are blocked even before
zone refill. NPTH hole clearance is checked independently of copper clearance.
The shared voltage policy reserves0.6mm around all60 discovered PT switching
nets,2.5mm around ignition collectors and0.3mm around battery supplies.

Checkpoint:174 placed,60 short same-side local pad connections routed at0.2mm;
107 local pairs intentionally remain unrouted. Global CAN, harness, heater
power paths, main-control signals, ground distribution and long rail links
remain for subsequent routing. This is not complete WBO routing or a supply
decoupling/thermal approval. In particular, local rail routing and ground vias
must be completed before use. All non-WBO footprint geometry/pad nets and all
original copper IDs/geometry are asserted unchanged. Reapplication to an
already routed WBO board is rejected.

`wbo_local_checkpoint.json` records actual placements, completed/pending pairs,
input/output SHA256 and shared voltage-policy provenance. The test input was
the PCB owner's1262-part prepack snapshot, input SHA256
`a1e919fd6ab78ba3482a52c7e49fb6cc0dba6e6f6fe0ef6786ac8af731aef197`.
An isolated diagnostic DRC retained all fixed components and WBO while removing
only other not-yet-placed components. It used the real project rules plus a
stronger explicit0.6mm rule for the60 domains (no relaxation/exclusions).
There were **zero WBO copper/hole/short/track-width violations**. Existing donor
DRC failures, unconnected items and WBO silkscreen collisions remain, recorded
in the report. This is explicitly not a full-board DRC pass.

CLI (use separate output, not the PCB owner's original):

```sh
python3 route_wbo_local.py input.kicad_pcb output.kicad_pcb \
  --fixed input.fixed.json --report local-report.json
```

The fixed JSON contains `fixed_references`. PCB copy and full diagnostic DRC
are local ignored artifacts in `board/build/wbo_local/`; committed JSON is the
compact checkpoint record. Re-run full-board DRC after integration and later
packing/routing. Source hardware license and physical measurements remain
tracked by the WBO engineering documents; this checkpoint adds no qualification.
