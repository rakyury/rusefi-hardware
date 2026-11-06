# WBO CAN logic routing — 2026-10-28

Baseline: `6fb8d7726a9c22174ac8cb09caf3d497bd586b62`.
Final PCB SHA256: `cf36d99bb312769ed73cdec0149b5d2e6b9fb01143e814fb0145150245b02206`.

## Electrical contract

U5602 is STM32F042K6T6, LQFP32. PA11/pad21 is CAN_RX and PA12/pad22 is CAN_TX (AF4), per [ST datasheet tables13–14](https://www.st.com/resource/en/datasheet/stm32f042k6.pdf). U5605 is TJA1051T/3/1J: pin1 TXD input, pin4 RXD output, pin5 VIO adjusts digital levels to the MCU supply ([NXP datasheet sections6–7](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf)). Exported core.net has U5602.17 and U5605.5 on WBO1_3V3, U5605.3 on +5V_CORE. These are logic signals, not the CANH/CANL differential pair. Firmware AF configuration and actual board supply/timing measurements remain separate validation tasks.

## Change

RX first: U5602.21 -> via(169.5,63.75) -> U5605.4; 5 tracks, 8.799658 mm.
TX second: U5602.22 -> via(169.5,62.75) -> U5605.1; 4 tracks, 8.835526 mm.
Both use F.Cu/B.Cu, 0.20 mm tracks, one 0.65 mm through-via with 0.30 mm drill. Exact UUIDs and dimensions are in routes.json. No component placement or schematic/BOM/netlist changes.

The guarded route module checks device, pin, supply and placement contracts, all-layer existing copper/HV constraints, drill spacing and pad mask separation. Both nets preflight before board mutation; RX becomes an obstacle for TX. Existing geometry is never overwritten. The functional builder applies these plans before zone refill and preserves them from dangling-copper cleanup. Completed nets are removed from the placement report's pending list.

## Native and independent evidence

Pinned KiCad9.0.9 image: `sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.

- Full connectivity: **2099 -> 2097**. KiCad connectivity BFS independently reaches all 8 RX objects (2 pads,5 tracks,via) and all 7 TX objects (2 pads,4 tracks,via), confirming both endpoint connections.
- Full native DRC after refill: **zero findings involving any of the 11 new copper UUIDs**. Existing categories: capped clearance503/width199, dangling vias14/tracks4; silk0/library mismatch0. Capped counts are not a total-error or progress measure.
- Identical before/after scoped fixtures at x162..173/y59..70 retain complete intersecting footprints/copper/zones on every layer and refill polygons. Both have exactly the same ten dangling-track violation signatures, no added violation signatures. Commands/hashes are in the accompanying provenance and prepare logs.
- A preliminary unfilled candidate exposed two hole-to-stale-GND-fill errors; it was rejected. Accepted full-board refill removes both. Baseline was independently refilled under the same rules for comparison; no rule exclusions or reductions were introduced.
- Parsed board delta: 9 segments and2 vias added, all original tracks/pads/footprints/net assignments unchanged. Of16 zones, only In1 GND UUID424ddee3-374b-41a8-85b8-c40338f4eff0 has changed filled polygons; its settings and outline are unchanged.
- Native polygon BooleanSubtract measured removed area2.0428198496705mm², of which2.0428198284895mm² lies around the two vias, bbox(168.9245,62.1745)–(170.0755,64.3255). Remote fracture-rounding sliver is2.1181e-8mm²; added slivers total6.2935e-9mm². No other region changed.
- Pad/net audit:1092positions,3464assignments,zeroerrors;20shuntpaste apertures preserved and sense pads Cu-only.
- 23native board tests,36core tests,18strictcosting tests passed. Assembly stays1047fitted,3210SMTlands,162THTlands. Monetary outputs are unchanged; only PCB provenance binding changes.

Full final reports are under hardware/design/board/gdi6_candidate. Board still has2097unconnected items and unresolved DRC/ERC issues; it is not a fabrication or engine release. No delivery PDF/Excel revision is claimed here; integration owner updates those after cherry-pick.
