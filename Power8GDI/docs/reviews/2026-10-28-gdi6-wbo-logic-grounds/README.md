# WBO MCU and bypass ground returns — 2026-10-28

Baseline: `d35e9ab18a8e32a06d656628f132f3e9dfc8102f`.
PCB SHA256: `e1887db8720d0945f611a9e5fe935d72f429a886bd382a77690af20472098e17`.

Three local connections to In1 GND: MCU U5602 pins16/32 and nearby C5612 pin2. [ST STM32F042x datasheet Table13](https://www.st.com/resource/en/datasheet/stm32f042k6.pdf) identifies LQFP32 pins16 and32 as VSS. C5612 is an existing100n bypass on WBO1_3V3 in the analog sheet, not assumed to be a dedicated MCU decoupler. Parts, pin assignments, nets and values remain unchanged. These ground returns do not complete the MCU supplies, bypass routing, analog circuitry or WBO control.

## Geometry

All tracks on F.Cu, width0.25mm. Each terminates in one through-via0.65mm diameter/0.30mm drill:

| Source | Start mm | Via mm | Length mm |
|---|---|---|---|
| C5612.2 | 180.15295,66.975 | 180.15295,67.975 | 1.000000 |
| U5602.16 | 169.37795,60 | 169.37795,61.25 | 1.250000 |
| U5602.32 | 174.97795,68.35 | 176.22795,68.85 | 1.346291 |

The guarded generator checks device/endpoint/supply contracts and every planned segment/via against all-layer copper, voltage domains, masks and holes before adding any object. It rejects partial/changed routes and is idempotent. Existing copper is preserved by the builder cleanup hook. Exact UUIDs are in routes.json.

## Validation

Pinned native KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity: **2092→2089** unconnected items.
- Full DRC: zero findings on the6newUUIDs. Reported clearance501/width199 are capped samples, not full counts; old dangling via14/track4 remain, silk/library mismatch0.
- Scoped before/after x165..184/y57..72 retains complete intersecting obstacles on all layers and refills zones. Both reports have the same17violation signatures, no added signatures. Reports include native command/hash provenance.
- Root tokenized full-board comparison: exactly3tracks+3vias added, all4602old top-level objects unchanged, including footprints/pads/nets/rules/complete zone fills. Agent separately verifies all2680old copper objects, including CAN/VIO/RESET/U5610ground.
- Native BFS verifies each pad-to-via link. All3vias contact the same single filled In1 GND outline in zone424ddee3-374b-41a8-85b8-c40338f4eff0. In one disposable copy, removing only that zone makes all3native contacts false. See ground_connectivity.json and independent_review.md. An initial root proof script hit a SWIG object-lifetime error while repeatedly loading copies; keeping one negative-control board alive fixed the script, without changing the PCB.
- **44native board tests +18strict costing tests PASS**. Pad/net audit:1092positions,3464assignments,zeroerrors. All20shuntpaste apertures and Cu-only sense pads preserved.
- Assembly1047fitted/3210SMTlands/162THTlands unchanged. BOM, netlist, schematic and financial JSON outputs unchanged; only the costing PCB hash is updated.22artifact hashes verified.

The board remains incomplete with2089unconnected items and inherited DRC/ERC findings. This is not a manufacturing release. Main GDI6 chat owns delivery PDF/Excel refresh after integration.
