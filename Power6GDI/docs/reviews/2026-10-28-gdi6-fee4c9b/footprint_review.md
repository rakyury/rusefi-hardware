# Independent footprint binding review — GDI6 fee4c9b

Reviewed on 2026-10-28, read-only against commit
`fee4c9b7beda8ac3931d22d46c5a514cdb3cd8e0` from
`C:/Users/User/Documents/Codex/2026-10-25/x20/work/sport-gdi6`.
The working checkout had advanced to `3c65849`; all conclusions below use
`git show` or a `git archive` snapshot of **fee4c9b**, not the moving HEAD.
No files in that repository were modified. Full native DRC is owned by the
integration lead and was not rerun in this review.

## Finding: P2 — ten fitted shunts have no solder-paste apertures

Affected library files under `Power8GDI/hardware/design/gdi/Power8GDI_GDI.pretty`:
`REF_R12`, `REF_R21`, `REF_R22`, `REF_R26`, `REF_R45`.
Affected actual references: **R203, R212, R213, R215, R221, R303, R312, R313,
R315, R321**.

In `REF_R12.kicad_mod:94–118`, physical terminals 1/4 have only
`F.Cu F.Mask`; Kelvin taps 2/3 have only `F.Cu`. There is no `F.Paste`
or `B.Paste` object anywhere in any of these five files. The actual ten
board instances likewise contain zero paste pads and zero paste graphics.
Checking all board drawings and other footprints found no F.Paste object
intersecting any of their footprint bounding boxes, so this is not a separate
aperture implementation elsewhere on the board. Pads are ordinary roundrects,
not custom pads carrying hidden paste primitives.

The BOM identifies these as fitted surface-mount parts, selected
`WSLP1206R0100FEA`. A stencil derived from this PCB will therefore supply no
paste at their twenty physical solder lands. This leaves an assembly gap
unless a separately specified dispensing/hand-solder process is deliberately
used. The new copper-land dimensions alone do not fix it.

This omission is **inherited**, not newly introduced by fee4c9b: its parent
`REF_R12` also has zero Paste layer mentions. It remains a concrete deficiency
in the updated footprints/actual PCB and is relevant before PCBA release.

Recommended owner action: define reviewed paste apertures for terminals 1/4,
keep copper-only Kelvin taps 2/3 free of paste/mask openings, regenerate the
derived footprints and PCB, and check exported stencil geometry. Add a check
that a fitted SMT shunt has two intended terminal paste regions; the current
land-size/net-tie test does not verify stencil coverage. Do not modify upstream
source footprints to implement this correction.

## Checks without additional binding findings

Using pcbnew from KiCad 9.0.9 on the immutable snapshot, compared **51 positions
and 246 numbered pad objects** against `core.net`: zero pad/net mismatches.
This includes duplicated MOSFET drain/paste subpads as separate pad objects.
The targeted positions comprise 24 selected GDI MOSFETs, ten shunts, two clocks,
eight GDI bulk capacitors, C1511, C1533/C1538 and C5208–C5211.

- The ten actual shunts have `net_tie_pad_groups "1,2" "3,4"`; no whole-device
  `1,2,3,4` grouping remains in them. The separate F.Cu polygons overlap each
  same-terminal power land and Kelvin tap without bridging the two terminals.
  The sense-net assignments agree with the schematic. R221/R321 are the
  separately documented VCCIO shunts with unused sense taps, not injector
  current shunts.
- For every targeted GDI-derived footprint, loaded its committed library
  definition, applied the actual PCB position/orientation, and compared pad
  number, position, size, angle and layer set. No geometry discrepancy was
  found. The builder's switch from source cloning to reviewed library geometry
  is reflected in the actual PCB.
- All 24 GDI MOSFETs carry the selected IPD60N10S4L12ATMA1 value and consistent
  pad numbering/net assignments. The library drain land remains 6.4 by 5.8 mm,
  lead lands 2.2 by 1.2 mm. This is an artifact-consistency check, not a fresh
  manufacturer package or electrical qualification.
- C1511 is actually 1812. C1533/C1538 use the new CGA9P3_2220 geometry with
  1.3 by 4.5 mm lands and a 4.5 mm copper gap, mirrored onto B.Cu. C5208–C5211
  remain 1210, 47 uF/16 V, connected to +5V_CORE/GND.

## Explicit check of the 50 V capacitors versus 65 V boost

Read `HW_B58_GEN2_INJECTOR_REVIEW.md` before checking the actual assignments.
The suspected 50 V-on-boost mismatch is **not present**:

| References | Positive pad net | Negative pad net | Selected/schematic rating |
|---|---|---|---|
| C205 / C305 | VBAT_GDI_A / VBAT_GDI_B | GND | 1300 uF, 50 V |
| C206 / C306 | PTA_+Batt_filtered / PTB_+Batt_filtered | GND | 1300 uF, 50 V |
| C207, C209 / C307, C309 | PTA_VBOOST / PTB_VBOOST | PTA_Vdrive_shunt / PTB_Vdrive_shunt | 470 uF; selected UBY1K471MHL, 80 V in BOM ratings |

Thus the 50 V parts are on battery/input-filter nodes. Their input transient,
inrush and ripple qualification remains outside this check. Similarly, an
80 V nominal rating does not prove acceptable overshoot/lifetime at 65 V boost;
the committed review already records this limitation.

## Reproduction and limits

The audit snapshot and script are preserved locally under this review worktree:
`Power8GDI/hardware/design/board/build/gdi6_audit/` (ignored scratch).
`snapshot.zip` was generated with `git archive fee4c9b` for the candidate board,
core.net, BOM, GDI library/mapping/parser and custom capacitor footprint.
`check.py` loads only the snapshot via pcbnew and writes `results.jsonl`.
The candidate board SHA256 as archived is
`3d1a64d1bb783f57161f65aab5fa8819ccc23ba525de4d95ff3d8f3089b2d419`.

No source generators, schematic or BOM files were run with write access to
the owner's repository. Its `git status --short` remained empty. No internet
sources were needed: findings concern committed code and physical artifacts.
Manufacturer recommendations quoted by the project were not independently
revalidated here. Solder-volume design, hot-current/SOA, thermal performance,
actual injector timing, EMC, complete routing and DRC closure are not approved
by this review. The integration lead separately owns current native DRC findings.
