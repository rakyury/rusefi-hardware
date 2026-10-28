# CAD-06 reproducible concept assembly — 2026-10-21

## Scope and source

This stage restores CAD generation/testing from a fresh source checkout. The
existing design is a conceptual 265 × 185 × 54 mm enclosure around a nominal
245 × 165 × 1.6 mm PCB envelope. Geometry is generated entirely from
`mechanical/assembly_manifest.json` with the dependency versions pinned in
`mechanical/requirements-cad.txt`. The deprecated enclosure parameter snapshot
now points to that source. Generators and renderer have no import-time writes.

The CLI exports only to the supplied `--output-dir` (default
`mechanical/build/assembly`), preserving tracked source files. Tests consume
that default or `POWER8GDI_CAD_OUTPUT`. Missing CAD is an explicit failure.
Generated manifests tie exports to current source and generator hashes; file
hashes catch missing, replaced or stale assets. STEP import and STL inspection
check the actual artifacts, not merely the existence of a previous PASS report.

## Measured concept interference and correction

OCCT intersection of the original nominal base and PCB was
**77.32659724553022 mm³**. The four perimeter bosses at X = ±124, Y = ±84 mm,
radius 5.9 mm intersected the rectangular board corners. The prior tests checked
only overall board/interior sizes, so they did not detect this interference.

The conceptual perimeter screw centres move to X = ±128, Y = ±88 mm and boss
radius becomes 4.5 mm. Lid hole centres follow the same manifest parameters.
The outer enclosure, PCB envelope and PCB support coordinates remain unchanged.
This resolves the nominal clash without inventing board corner cutouts. It is
not a verified fastening, machining, thread-engagement or tolerance design.

The generator now rejects invalid/disconnected/zero-volume parts and any
positive-volume pair intersection above 1e-6 mm³ before publishing exports.
Boundary contact at intended supports is allowed. Fresh STEP artifacts undergo
the same interference checks after import; all STL meshes must be closed and
have volumes within 0.2% of their corresponding solid volumes.

## Reproduction and evidence

From the repository root:

```text
python -m pip install -r Power8GDI/mechanical/requirements-cad.txt
python Power8GDI/mechanical/build_assembly.py --output-dir Power8GDI/mechanical/build/assembly
python -m unittest discover -s Power8GDI/mechanical/tests -v
python Power8GDI/mechanical/render_views.py --input-dir Power8GDI/mechanical/build/assembly --output-dir Power8GDI/mechanical/build/renders
```

Validated toolchain: Python 3.12.10, CadQuery 2.8.0, cadquery-ocp 7.9.3.1.1,
VTK 9.6.2 on Windows. Transitive dependency versions are pinned alongside these.
An optional `--manifest` supports separate concept variants; the standard tests
deliberately require the repository's canonical source, preventing accidental
validation of a different design.

Results: generation produced **18 valid solids, five STEP files and 18 closed
STL meshes**; **14 tests passed** (10.939 seconds on the final source state).
All imported STEP solid-pair interference checks passed at the stated numerical
threshold. Six 1500 × 1050 PNG views were generated; assembly and exploded views
were visually inspected. `git diff --check` passed. No generated STEP/STL/PNG is
committed; the outputs are under `mechanical/build/assembly` and `build/renders`.

Reported nominal clearances are 5 mm PCB-to-inner-wall on X and Y, 17.4 mm
tallest mock component to lid, 5 mm connector envelope to lid, and 1.4 mm
connector body to PCB top. These are envelope separations without tolerances,
pins, seals or actual component geometry.

## Remaining blockers

- Exact TE header variants, manufacturer STEP models, footprint/STEP alignment,
  connector aperture dimensions, latches, harness and seal clearances are pending.
- Routed PCB shape, placement, real component heights, pads/copper and mounting
  holes have not been matched to the concept envelope.
- Gasket design/IP rating, machining tolerances, fasteners, thread engagement,
  material, heat paths, thermal/EMC and physical fit require engineering review
  and prototype measurements.
- No enclosure or PCB manufacturing release, real assembly fit, engine suitability
  or automotive qualification is asserted. Renders show conceptual geometry.
