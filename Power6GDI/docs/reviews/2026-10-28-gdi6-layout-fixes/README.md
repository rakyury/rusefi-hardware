# GDI6 PCB repair checkpoint — 2026-10-28

Baseline: `2f4a527f3ff661de522f60de78b059fae9a89f07`.
PCB SHA-256 after repairs: `25aa498aa4491da8bf1901736c84a1affb26e64c01c6b818565fbd7b30f6967a`.

Two 0.6 mm F.Cu GND tracks now join the existing R215/R315 return vias to their power pads 4. No original via, pad, track, net or zone was removed or moved. Five silk segments per Y201/Y301 were adjusted; the pin-1 marker remains. The footprint extractor and board generator retain these repairs on regeneration.

## Evidence

Pinned KiCad 9.0.9 image: `kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.
Full candidate reports and exact native command provenance are in `hardware/design/board/gdi6_candidate/`. The two scoped reports alongside this document retain surrounding foreign-net obstacles and full connectivity checks, with exact command arguments in their provenance files.

- Full-board unconnected count: 2101 -> 2099.
- Uncapped dangling-via category: 16 -> 14; both repaired vias have no remaining findings.
- Uncapped silk-over-mask category: 12 -> 2; ten Y201/Y301 findings removed.
- Scoped native DRC: no finding on either new track or repaired via. R215 scope retains 14 clearance, 14 width and 12 dangling-track findings elsewhere; R315 retains 12, 14 and 9 respectively.
- Pad/net comparison: 1092 physical positions, 3464 assignments, zero errors.
- All 20 shunt paste apertures preserved; sense pads remain Cu-only.
- Parsed PCB delta: only two added tracks and ten silk endpoint edits, allowing ordering of pad-layer lists after KiCad serialization.
- 17 board tests, 36 core tests and 18 strict costing freshness tests passed; logs included.
- Assembly remains 1047 fitted positions, 3210 SMT lands and 162 THT lands. Cost inputs change only the PCB hash; monetary assumptions and component quantities are unchanged.

No rules were relaxed or exclusions added. Capped clearance/width totals are not a progress measure. The board remains incomplete with 2099 unconnected items and unresolved DRC errors. This is not manufacturing or engine qualification. Delivery PDF/Excel provenance requires refresh by the integration owner after cherry-pick.
