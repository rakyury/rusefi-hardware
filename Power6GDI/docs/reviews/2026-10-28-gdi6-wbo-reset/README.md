# WBO supervisor reset branch — 2026-10-28

Baseline: `0e4c4268af444eb32dea0d345b211eb7728dc3d4`.
PCB SHA256: `7e7872186f98b95cc92002db7e7e9ce3789c719f5df7182711846a7bdf729be0`.

Connect existing TPS3808G33 supervisor U5612.1 (RESET) to existing 10k pull-up R5662.1 on WBO1_nRESET. R5662.2 is WBO1_3V3. The [TI TPS3808-Q1 datasheet](https://www.ti.com/lit/ds/symlink/tps3808-q1.pdf) describes the active-low open-drain reset output. No device, pin assignment, value or netlist changes are made. This is only the supervisor/pull-up branch: the MCU/reset capacitor/debug branches and supply distribution remain incomplete.

Seven B.Cu segments, width 0.20mm, total 7.801496mm; no vias. Exact coordinates and UUIDs are in routes.json. The guarded generator checks device, endpoint, supply and pull-up contracts plus actual copper/voltage-domain and hole clearance before adding anything. It rejects partial/changed routes and is idempotent. The builder preserves the new segments during cleanup. Only this exact endpoint pair is removed from the pending report.

## Validation

Pinned KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity: **2094 → 2093** unconnected items.
- Full DRC: no findings on any of the seven new UUIDs. Reported clearance504/width199 are capped samples, not complete counts; prior dangling via14/track4 remain, silk/library mismatch0.
- Scoped before/after x168..179/y80..89, retaining intersecting full obstacles and refilling zones: same40violation signatures, no new signatures. Reports and hash/command provenance are included.
- Root tokenized full-board comparison and independent agent UUID comparison: exactly7segments added; all original footprints, pads, copper, vias, nets, rules, zones and filled polygons unchanged.
- Native BFS verifies the reset endpoints connected by7segments; existing CAN TX/RX, VIO and both ground returns remain connected. See independent_review.md.
- **33native board tests +18strict costing tests PASS**. Pad/net audit:1092positions,3464assignments,zeroerrors. All20shuntpaste apertures and Cu-only sense pads preserved.
- Assembly remains1047fitted /3210SMTlands /162THTlands. BOM, schematic, netlist, prices and financial JSON outputs are unchanged; costing input only receives the new PCB provenance hash.22artifact hashes checked.

The board remains incomplete with2093unconnected items and inherited DRC/ERC findings. This is not a manufacturing release. Main GDI6 chat owns delivery PDF/Excel refresh after integration.
