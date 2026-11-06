# Independent GDI6 PCB audit — fee4c9b

Audited immutable revision: `fee4c9b7beda8ac3931d22d46c5a514cdb3cd8e0`.
The schematic/BOM owner's working checkout was not modified. The review used
a separate Git archive and pinned KiCad 9.0.9 with networking disabled.

## Finding: missing paste apertures on ten fitted shunts

**Closed in `4659d88ff8ec5dd94638e35c550a4f8599e992f4`.** Independent
comparison of Git blobs confirms exactly 20 F.Paste additions to power pads
1/4, with sense pads 2/3 remaining Cu-only. Removing those 20 flags makes the
parsed PCB identical to the audited baseline; the netlist is byte-identical.
The new normalized PCB SHA256 is
`fd6eac9f2f58decc4784a1798c5549be44b5b30f6b08d3ae6b5db59f9506fd1a`.
See `stencil_fix_independent.json`. Full DRC was not repeated for this paste-only
change. This closes the missing-aperture finding, not routing or manufacturing
qualification. The original finding below is retained as historical evidence.

The updated derived footprints and actual PCB have no F.Paste apertures for
the two physical solder lands of each of these resistors:

| Actual references | Derived footprint |
|---|---|
| R203, R303 | Power8GDI_GDI:REF_R12 |
| R212, R312 | Power8GDI_GDI:REF_R21 |
| R213, R313 | Power8GDI_GDI:REF_R22 |
| R215, R315 | Power8GDI_GDI:REF_R26 |
| R221, R321 | Power8GDI_GDI:REF_R45 |

Power pads **1 and 4** are 1.93 × 1.65 mm, with `F.Cu` and `F.Mask` only.
Sense pads **2 and 3** are 0.15 × 0.15 mm, `F.Cu` only; their absence of paste
is intentional and is not this finding. No alternative paste graphics exist
in these footprints or at board level. Thus 20 physical power-land apertures
are missing from the stencil definition. This affects paste-based assembly;
it is not a claim that the documented count of 3210 copper solder lands is
arithmetically wrong. Copper solder lands and stencil apertures differ.

Proposed correction, sent to the hardware owner: define paste for power lands
1/4 in the derived library/generator, preserve the sense pads and two Kelvin
net-tie groups, update the actual PCB and verify the generated paste output.
Do not edit the immutable upstream donor. Add regression coverage for this
property; pad-net agreement and ordinary DRC do not establish paste coverage.

## Reproduced evidence

- All 19 normalized artifact hashes pass; netlist and PCB match the supplied SHA256.
- Native pad check: 1092 positions, 3464 assignments, 34 DNP, no errors.
- Full connectivity residual: **2101**, compared with 2099 in baseline 013f467.
- Native DRC sample: 504 clearance, 199 width, 16 dangling vias, 4 dangling
  tracks, 12 silk-over-copper: **735 reported violations**, 499 unconnected items.
- Saved DRC has 740 violations. Clearance/width/unconnected reports reach caps;
  the 735/740 difference must not be treated as an improvement or regression.

The uncapped categories do support specific comparisons: two new GND dangling
vias at (80.175, 32.06498) and (184.06498, 71.305), near R215/R315 respectively;
and ten new silk-mask overlaps on Y201/Y301. They remain open layout work.
Coordinates alone do not establish the cause of the two missing connections.
Exact objects and UUIDs are retained in `uncapped_delta.json`.

The 50 V C205/C206/C305/C306 parts are input-side capacitors on battery/filtered
battery nets, not the 65 V boost node. No voltage-placement defect is asserted
for them. Injector waveforms, boost transients, thermal and engine qualification
remain outside this static audit. Manufacturing remains blocked.
