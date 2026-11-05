# GDI6 independent PCB audit and cross-chat ownership

Audited commit: `013f4675dd659b82e0b83a1704589ad4e95c8942`, branch
`codex/sport-gdi6-20261025`, draft PR #4. Date: 2026-10-28.

The user changed the active target to six DI, six optional PI, two HPFP,
six ignition channels, two motor bridges and one onboard wideband controller.
One external EGT channel remains the working architecture. The authoritative
scope is `docs/SCOPE_2026_10_25_SPORT_GDI6.md` in that commit, with the research
index in `docs/research/2026-10-25-sport-ecu/README_RU.md`.

The chat «Сравнить форки rusEFI» owns the GDI6 schematic, BOM, firmware and
client. The chat «R2 GDI 8» owns this independent PCB/DRC audit and proposed
infrastructure changes. This division was confirmed by both chats after the
user explicitly authorized coordination. No files in the other chat's working
checkout were edited; an archive of the named commit was extracted separately.

## Independently reproduced

- All 16 artifact-manifest file hashes match the committed files.
- KiCad pad contract: 1092 positions, 3464 pin assignments, 34 DNP, no errors.
- Full connectivity residual: **2099 missing connections**.
- No project DRC exclusions and no ignored rule-severity categories.
- Pinned KiCad 9.0.9 native DRC, using `board/run_drc.py`: 505 clearance,
  199 track-width, 14 dangling-via, 4 dangling-track and 2 silk-over-copper
  findings; 724 reported violations and 499 reported unconnected items.

The saved report had 721 reported violations, including 502 clearance findings.
The independent rerun reaches the same capped categories. These are truncated
samples, not an exact total or evidence that three new defects appeared.
No shorting-items category was reported; this does not prove the entire board
has no shorts, especially while the known shunt net-tie defect remains in this
audited revision. The hardware owner is already correcting that defect.

Direct CLI runs against bind-mounted project files produced 199 additional
missing-library findings. They are diagnostic environment failures, not accepted
PCB results. The committed evidence uses the project's existing wrapper, which
copies the unchanged board/rules and custom libraries into Linux temporary
storage before native DRC. These library findings then disappear.

## Preserved work and next integration gates

Old GDI8 work remains available as `ab7dd27` (thermal-via-aware placement and
control-return candidates) and `71361c4` (guarded BOOT rule and fixture-rule
ordering). The placement candidate has 138 segments, 29 vias and no rejected
local branches on its old prepack; native DRC of that relocated cell is still
pending. The BOOT work has 13 passing tests, with native negative cases still
incomplete. Neither patch is automatically qualified for GDI6.

Next: audit the hardware owner's committed shunt/FET/BOM update; regenerate a
matching PCB; evaluate the power-placement and rule-order patches on that exact
netlist; then perform uncapped local checks before accepting routing changes.
Keep the original upstream layouts unchanged. Manufacturing remains blocked.
