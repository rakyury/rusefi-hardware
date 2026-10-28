# Frozen selection input

These unmodified exports are from git revision 013f4675dd659b82e0b83a1704589ad4e95c8942:
- Power8GDI/hardware/design/integrated_bom.csv
- Power8GDI/hardware/design/core.net
- Power8GDI/hardware/design/gdi/footprint_manifest.json

They pin the source of the engineering selection. Hardware updates and MPN annotations occur in the actual design; they must not silently replace this provenance. Approved deviations are explicit per-reference records in overrides.json. Replacing this snapshot is a reviewed source refresh, not a routine generation step.

Hash policy: these three frozen source files are stored with Git `-text` and SHA-256 covers their exact bytes, including original line endings. The generated selection and actual-design validation use SHA-256 after replacing CRLF with LF, consistently with the hardware binding report. Set `REQUIRE_BOM_BINDING=1` in integrated CI so a missing current-design report fails rather than allowing the untouched source baseline to skip.
