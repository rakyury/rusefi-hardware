# WBO logic-gate ground return — 2026-10-28

Baseline: `671da0b525696f09387f7624e7eba2d8e55a1824`.
PCB SHA256: `3a6f881bd42b702a6e085e7eddefbcd569296583262431f3ccb02c25484b4f9b`.

Connect existing U5610 pin3 to In1 GND. U5610 is SN74LVC1G08QDBVRQ1, the AND gate in the heater-permission logic. This is its logic supply return, not the heater power return. [TI datasheet section4](https://www.ti.com/lit/ds/symlink/sn74lvc1g08-q1.pdf) identifies DBV pin3 as GND and pin5 as VCC. Device, pin assignment, values and netlist remain unchanged. VCC/bypass routing U5610.5→C5640.1 and other unfinished connections remain pending; this step does not complete the gate circuit or qualify heater control.

Geometry: B.Cu track (178.8625,82.55)→(178.8625,81.8), width0.25mm, length0.75mm; one through-via0.65mm/0.30mm at the endpoint. Exact UUIDs are in routes.json. Guarded generation checks device/endpoint/supply contracts, all-layer copper/voltage-domain clearance, holes and via-to-mask clearance before mutation. Partial/altered branches are rejected; repeated execution is idempotent. The builder preserves this copper during cleanup.

## Validation

Pinned KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity: **2093→2092** unconnected items.
- Full DRC: no findings on either new UUID. Reported clearance503/width199 are capped samples, not total error counts; inherited dangling via14/track4 remain, silk/library mismatch0.
- Identical scoped fixtures x168..183/y77..90 retain intersecting complete obstacles on every layer and refill zones. Both have the same50violation signatures, no new signatures. Native reports and command/hash provenance are included.
- Root full tokenized-board delta: exactly1track+1via added; all4600old top-level objects unchanged, including every footprint, pad, trace, via, net, rule, zone and filled polygon. Independent agent verifies old copper signatures.
- Native BFS confirms U5610.3→via. IsConnectedOnLayer confirms In1 contact in the single filled outline of GND zone424ddee3-374b-41a8-85b8-c40338f4eff0. Removing only that zone in a disposable memory copy makes the native contact false. No mutation from this negative control is saved. See ground_connectivity.json and independent_review.md.
- **39native board tests and18strict costing tests PASS**. Initial costing freshness checks correctly failed while the assembly report still held the previous board hash; after assembly regeneration the full strict suite passed. No rules or checks were relaxed.
- Pad/net audit:1092positions,3464assignments,zeroerrors. All20shuntpaste apertures and Cu-only sense pads preserved. Assembly1047fitted/3210SMTlands/162THTlands unchanged. BOM, schematic, netlist and financial JSON outputs unchanged; costing input only receives the new PCB hash.22artifact hashes verified.

The board remains incomplete with2092unconnected items and inherited DRC/ERC findings. No manufacturing release is claimed. Main GDI6 chat owns delivery PDF/Excel refresh after integration.
