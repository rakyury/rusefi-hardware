# LM76003 intrinsic land clearance

The [TI LM76003-Q1 datasheet](https://www.ti.com/lit/ds/symlink/lm76003-q1.pdf),
RNP0030B/E example board layouts, specifies 0.5 mm pitch and 0.25 mm land width:
the nominal adjacent gap is therefore 0.25 mm. The selected KiCad footprint
has these dimensions and a 1.8 x 4.5 mm exposed pad. Its extended 1.025 mm land
length differs from the example's 0.75 mm; this decision concerns transverse
spacing only and is not a claim of complete footprint equivalence.

`board/package_clearance.py` provides four explicit 0.25 mm pad-to-pad rules
for U5200 pairs 5–6, 6–7, 19–20 and 22–23. Both objects must be pads of U5200
and match the exact pair. No other footprint, track, via or zone is covered.
The normal 0.3 mm battery rule remains elsewhere. This replaces an incompatible
generic target at those manufacturer-defined lands; it does not suppress DRC.
Validate the device, footprint, pad dimensions, pitch and orientation using
`validate_lm76003(board)` before appending `lm76003_rule_text()` after general
voltage rules. Geometry changes must fail for renewed review.

Native KiCad 9.0.9 verification on a spatial copy of the actual combined board
retained every nearby footprint and complete crossing obstacle on all layers.
Clearance counts were 70 before and 66 after, below the report cap. Exactly the
four pad pairs disappeared; all five offending escape tracks remained errors.
Widening pad 6 to 0.27 mm failed the geometry guard and produced two native
0.25 mm-rule violations. Evidence and source-board hash are in
`hardware/design/board/lm76003_package_review.json`.

BOOT escape routing requires a separate bounded geometric review. No track
exception is included here. Manufacturing process, cleanliness/coating,
transient and operating qualification remain unverified.
