# UI-05 offline editor validation — 2026-10-21

Scope: the existing separate PyQt6 configurator under `Power8GDI/configurator`.
This change adds document lifecycle protection and widget-level regression
coverage. No transport, ECU writes, firmware or hardware changes are included.

## Implemented behavior

- New / Open / Close ask Save, Discard or Cancel for edited documents. Save
  cancellation and write failure cancel the pending replacement or close.
- The modified marker follows `QUndoStack`'s clean checkpoint. Undo or redo to
  the saved version marks the document clean; branching away from a discarded
  saved checkpoint remains dirty. Undo/redo actions reflect stack availability.
- A successful Save As changes the active path. Failed Save As retains the
  original path, title and clean checkpoint.
- File actions commit an active table delegate before checking unsaved state
  or saving. Ctrl+S therefore includes the text currently being edited.
- Z-layer edits retain their original table and layer during undo and redo,
  including when another layer or a 2D table is visible.
- Values with more than two decimal places keep their exact float text through
  display/edit cycles; opening a cell and pressing Enter cannot round it.
- Keyboard selection in the table tree updates the displayed table. Valid
  custom names without a ` / ` delimiter appear in a Calibration group.
- Empty projects, invalid JSON and non-text descriptions report a load error
  while preserving the active project, path and undo history.

## Reproduction

From `Power8GDI/configurator` using Python 3.11 or newer:

```text
python -m pip install -e ".[dev]"
python -m pytest tests -q
python -m unittest discover -s tests -v
```

The real Qt GUI tests are `tests/gui/test_app.py`. They use QApplication,
MainWindow, QTableWidget's editing delegate and QTest keyboard events. Only
native file pickers and message-box responses are replaced to exercise
deterministic Save/Discard/Cancel and error outcomes. Actual JSON files are
saved and reloaded in temporary directories. Qt uses `offscreen` unless the
caller sets `QT_QPA_PLATFORM`.

Results on 2026-10-21: `python -m pytest tests -q` completed with **60 passed,
8 subtests passed** (36 GUI cases plus 24 existing model/codec tests).
`python -m unittest discover -s tests -v` completed with **24 tests OK**.
`git diff --check` passed. These results apply to the UI branch before
integration of parallel MAP/FW work; the integration lead must rerun the suite
against the combined changes.

Environment tested: Windows, Python 3.12.10, PyQt6 6.11.0, Qt 6.11.2 and pytest
9.1.1. The workspace virtual environment was supplied by the integration lead;
no system-wide package or configuration changes were made.

## Limits

Headless widget tests verify editor behavior; they do not establish visual
layout quality, platform-native file-dialog behavior, hardware suitability or
engine calibration validity. Project values remain examples. ECU connection,
Burn/Flash and live telemetry remain unavailable. Hardware, thermal, EMC,
fault-injection and engine validation were not run.
