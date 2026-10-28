# WBO MCU VDD bypass connection — 2026-10-28

Baseline: `bc8b1f55dbf7c164b2dc26a3c03a47085a1e7705`.
PCB SHA256: `5c1f064233a1a4ba51e6c8f209de365f30a4cd411869d71b7ece4dd3e51703e0`.

Connect U5602.1 to existing C5612.1 on WBO1_3V3. [ST STM32F042x datasheet Table13 and section6.1.6](https://www.st.com/resource/en/datasheet/stm32f042k6.pdf) identify LQFP32 pin1 as VDD and require local supply bypassing. C5612 is100n; its ground-to-In1 return was completed in the preceding commit. This new connection creates the local VDD-to-capacitor branch; it does not complete the upstream regulator feed or qualify MCU/WBO operation. C5612 belongs to the source analog sheet, but already shares the same WBO1_3V3 rail; neither schematic nor nets change.

One F.Cu track, width0.25mm, length2.25mm, from(176.35295,66.975) to(178.60295,66.975), no vias. UUID in routes.json. Device, supply endpoint, bypass-ground net/placement and copper/hole/voltage-domain checks precede mutation. Repeated application is idempotent. Changed widths and truncated collinear branches are rejected instead of silently covered. The builder preserves the new segment during cleanup.

## Validation

Pinned native KiCad9.0.9 image sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729.

- Complete native connectivity: **2089→2088** unconnected items.
- Full DRC: no findings on the new UUID. Reported clearance502/width199 are capped samples, not complete totals; inherited dangling via14/track4 remain, silk/library mismatch0.
- Identical scoped fixtures x165..184/y57..72 retain complete intersecting obstacles on every layer and refill zones. Before/after both have the same17violation signatures, no added signatures. Reports include command/hash provenance.
- Root tokenized full-board comparison: exactly1track added, all4608old top-level objects unchanged, including all footprints/pads/nets/rules/filled polygons. Agent separately verifies all2686old tracks/vias and their UUIDs/signatures.
- Native BFS confirms VDD→C5612 changes from disconnected to connected. C5612.2→existing ground via and native In1 contact remain true; existing VDDIO2 pin17→C5615.1 was already connected and stays unchanged. See independent_review.md. Net labels alone are not used as connectivity proof.
- **50native board tests +18strict costing tests PASS**. Pad/net audit1092positions/3464assignments/zeroerrors;20shuntpaste apertures and Cu-only sense pads preserved.
- Assembly1047fitted/3210SMTlands/162THTlands unchanged. BOM, netlist, schematic and financial JSON outputs unchanged. Only the costing PCB hash is updated;22artifact hashes verified.

The board remains incomplete with2088unconnected items and inherited DRC/ERC findings. In particular, local bypass connectivity does not prove completed upstream power distribution. No manufacturing release is claimed. Main GDI6 chat owns delivery PDF/Excel refresh after integration.
