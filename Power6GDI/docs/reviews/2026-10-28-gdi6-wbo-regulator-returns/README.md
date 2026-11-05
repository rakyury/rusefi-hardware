# WBO LT3042 ground returns — 2026-10-28

Baseline: `328b7ac3cbb18b5d159a098ff78bad652beaa347`.
PCB SHA256: `638900cd40914d65b20f752ccf2698f53bb84e6ac96d56a0a211c24fb287576f`.

Complete the existing output-capacitor ground return and IC ground-pin connection to the regulator's already grounded exposed pad. [ADI LT3042 RevC pp12–15](https://www.analog.com/media/en/technical-documentation/data-sheets/lt3042.pdf) defines GND pin8 and exposed pad11. The previous commit completed OUT10→MCU and separate OUTS9→Cout; these paths remain unchanged.

Two B.Cu tracks0.25mm:
- C5662.2(164.011038,91.028729)→U5604.11(161,85),6.738837mm.
- U5604.8(163.15,85)→U5604.11(161,85),2.15mm.

The original EP-to-via0.20mm track and existing0.65/0.30mm GND via at(159,83), UUIDd96e32b9-4b50-4783-8f84-acf18c3846ab, remain unchanged. No new via or duplicate EP connection is added. Device/pad contracts and that existing path are guarded. Copper/HV/hole checks finish before mutation; changed/partial/duplicate paths are rejected and repeated execution is idempotent.

## Validation

Pinned native KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity **2087→2085**. Native BFS confirms both new returns reach the existing via; native In1 contact is true.
- Input capacitor C5661.2 already reaches its own GND via at(156.988962,92.028729) and In1 before/after; it was not modified. During exploratory review, GetConnectedTracks returned a generic PCB_TRACK wrapper for a via, which caused an incorrect floating-island hypothesis. UUID-based traversal corrected it before implementation; no redundant third track was added.
- Full DRC: zero findings on the2newUUIDs. Reported clearance504/width199 are capped samples; inherited dangling via14/track4 remain. No silk/library mismatch findings.
- Scoped before/after x157..184/y62..93 retains complete intersecting obstacles on every layer and refills zones; the same123violation signatures remain, none added. Native reports include command/hash provenance.
- Root tokenized full-board comparison: exactly2tracks added, all4625old top-level objects unchanged, including complete filled polygons. Independent review verifies all2703old tracks/vias unchanged. The regulator power path still reaches MCU VDD without the sense branch; power/sense meet only inside Cout.
- **63native board tests +18strict costing tests PASS**. Pad/net audit1092positions/3464assignments/zeroerrors. All20shuntpaste apertures and Cu-only sense pads preserved. Assembly1047fitted/3210SMTlands/162THTlands unchanged.22artifact hashes checked; BOM/netlist/schematic and financial JSON outputs unchanged, only costing PCB hash updated.

C5660.2 (SET bypass-capacitor ground) remains disconnected and needs a separate Kelvin return to Cout ground, rather than sharing the loaded EP return. Input power distribution and other WBO rail branches are not qualified by this change. Cout effective capacitance, ESR/ESL and layout stability require further validation; these ground connections are not evidence of measured LDO stability. The PCB remains incomplete with2085unconnected items and inherited DRC/ERC findings. No manufacturing release is claimed. Main GDI6 chat owns PDF/Excel delivery refresh.
