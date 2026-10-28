# Power8GDI concept CAD

This is a provisional enclosure/PCB/component clearance envelope. Connector
bodies and cavities are placeholders, not manufacturer TE STEP geometry. The
board has no routed copper or verified component placement. A collision-free
concept does not establish actual board fit or manufacturing readiness.

`assembly_manifest.json` is the single source of geometry dimensions, mount
locations, component envelopes and export tolerances. Edit that source and
regenerate. `enclosure_params.json` is a compatibility notice, not a second
parameter set. `generate_enclosure.py` forwards to the canonical generator.
Importing any generator or renderer constructs nothing and writes nothing.

From the repository root, with a Python 3.12 virtual environment:

```text
python -m pip install -r Power8GDI/mechanical/requirements-cad.txt
python Power8GDI/mechanical/build_assembly.py --output-dir Power8GDI/mechanical/build/assembly
python -m unittest discover -s Power8GDI/mechanical/tests -v
python Power8GDI/mechanical/render_views.py --input-dir Power8GDI/mechanical/build/assembly --output-dir Power8GDI/mechanical/build/renders
```

The default generation and test directory is `mechanical/build/assembly`.
To test another generated directory set `POWER8GDI_CAD_OUTPUT` to its path.
Both relative and absolute `--output-dir` paths are supported; absolute paths
avoid dependence on the invoking working directory. On Linux, rendering may
need an available EGL/X display or `xvfb-run -a` depending on the VTK platform.

Generation produces five STEP files, 18 STL meshes and a generated manifest.
The manifest records source and generator hashes, every exported file's hash,
CadQuery version, valid-solid checks, positive-volume collision checks and
nominal clearances. Files are built in a temporary staging directory; the
generated manifest is published last. STEP timestamps can differ between runs;
reproducibility means equivalent validated geometry, not byte-identical STEP.

Tests require current generated assets and CadQuery. Missing, stale or modified
assets fail rather than silently skipping. They reimport STEP geometry, verify
solid validity and size, test interferences, and inspect actual STL meshes for
open/non-manifold edges and volume agreement. Large generated assets belong in
the ignored build directory or a release artifact, not source control.

See `../docs/CAD_REPRODUCIBLE_CONCEPT.md` for the corner-boss correction,
validation evidence and remaining hardware/vendor-CAD blockers.
