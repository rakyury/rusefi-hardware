# WBO VIO bypass and ground returns — 2026-10-28

Baseline: `e47f09301d6e3de56d04d71d60d73330b8800069`.
PCB SHA256: `75e98a2a132238da55b954a4b55d0bde57f14ed8334183e136645a9238173bdf`.

## Local electrical purpose

U5605 is TJA1051T/3/1J. Connect its VIO pin5 to existing100nF C5618.1 on WBO1_3V3, and provide local GND returns from C5618.2 and the actual power-ground pin U5605.2 to In1 GND. Pin8 is the S mode input and is not substituted for a power-ground return.

[NXP TJA1051 Rev9 sections6–7/table7](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf) defines pin5 as the logic-level adapter supply, with up to0.5mA VIO current. Its VCC current is up to70mA dominant and110mA under the stated bus-short conditions. Track dimensions below are local engineering choices, not measured thermal/EMC qualification. U5605.3/C5613 and the upstream VIO/VCC supply connections remain unfinished; these three local branches do not make the complete transceiver operational.

## Geometry and reproducibility

- VIO: B.Cu (161.37795,67.055558) -> (161.37795,69.055558),2mm.
- C5618 ground: (162.92795,69.055558) -> via(162.17795,69.805558),1.06066mm.
- U5605 power ground: (166.32795,64.515558) -> (164.82795,64.515558) -> via(164.82795,62.765558),3.25mm.
- Four B.Cu tracks,0.25mm; two through-vias,0.65mm diameter/0.30mm drill. Exact UUIDs in routes.json.

All-layer copper/HV, pad mask and drill clearances are checked before mutation. Existing/partial conflicting routes are rejected; an already applied route is idempotent. The functional builder includes all added copper in preservation IDs before cleanup and refills zones. Parts, previous CAN routes, schematic, netlist, BOM and rules remain unchanged.

## Validation

Pinned native KiCad9.0.9 image: `sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.

Full connectivity **2097 -> 2094**. Full DRC has no findings on any of the6newUUIDs; silk/library-mismatch findings remain0, prior dangling via14/track4 remain. Clearance507 and width199 are capped samples, not complete totals.

Identical before/after scoped fixtures x158..172/y60..72 retain full intersecting obstacles and refill zones. Both contain the same9dangling-track violation signatures, with no new signatures. Native command/hash evidence accompanies the reports.

Independent parsed audit confirms only4tracks and2vias added; every old object, including all16zones and their filled polygons, is identical. Connectivity BFS confirms the VIO endpoints, each ground pad-to-via path and the existing CAN TX/RX paths. Native IsConnectedOnLayer confirms both new vias connected to In1 GND. In a disposable negative control, removing only the In1 GND zone makes both results false; both centers belong to its same single filled outline. See NATIVE_CONNECTIVITY_REVIEW.md for the API limitation and exact checks.

27native board tests and18strict costing tests pass. Pad/net audit:1092positions,3464assignments,zeroerrors. All20shuntpaste apertures and Cu-only sense pads preserved. Assembly remains1047fitted/3210SMTlands/162THTlands; financial JSON outputs are identical to baseline, with only the PCB provenance hash updated.

The PCB remains incomplete with2094unconnected items and unresolved DRC/ERC findings. No manufacturing or engine release is claimed. Integration owner refreshes delivery PDF/Excel after accepting this commit.
