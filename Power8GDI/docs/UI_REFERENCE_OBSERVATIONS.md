# Offline editor interface study — 2026-10-21

The user authorized read-only study of an already open EMU PRO desktop client.
The client visibly reported Disconnected / OFFLINE / NO ADAPTER. The study
covered the ALL, FUEL and BOOST workspaces, the fuel map table-to-3D switch,
and the boost map's visible gear-layer control. The ALL workspace was restored
after inspection. No calibration edits, file saves, ECU connection or writes
were performed. No private calibration values, files, images or proprietary
assets are included in this repository.

## Observed interaction patterns

- Category workspaces retain layouts of parameter trees, maps and log panels.
- A filter field sits immediately above the parameter tree.
- Axis labels and units appear alongside the map; a separate selector identifies
  the additional map dimension.
- The same map can be viewed as a colored numeric table or a 3D surface.
- Log traces have labels, units and acquisition rates; disconnected channels
  display missing-data states rather than fabricated live measurements.
- Connection and adapter status remain visible at the bottom of the window.

These are observations of the selected workspace, not an exhaustive claim
about EMU PRO capabilities or an implementation specification for its firmware.

## Applied to Power8GDI in this iteration

Added local map filtering by name, description, axes and units, with Ctrl+F and
a clear button. Filtering cannot change calibration values, the selected map's
Z layer, or the undo checkpoint. Existing offline status and distinct Z selector
remain visible. The already implemented document lifecycle protections and
precision-preserving edits were validated independently of this visual study.

## Next interface milestones

1. Saved workspace layout and dockable map/document panels.
2. Read-only 3D visualization of the selected Z slice, sharing the existing
   validated model and undo operations rather than maintaining separate values.
3. Typed parameter editors and descriptions backed by an explicit schema.
4. Imported offline log viewer before implementing real device telemetry.

None of these observations establish rusEFI protocol or memory-page compatibility.
