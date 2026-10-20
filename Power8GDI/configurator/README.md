# Power8GDI Configurator — separate desktop application

Offline Python/Qt calibration editor inspired by the architecture of
[rakyury/racing_dash](https://github.com/rakyury/racing_dash): a versioned document
model, a responsive editor, UI independent of hardware transports, tests.

**Status: 0.1.0.dev1 developer preview / OFFLINE ONLY.** The map values are examples,
not engine-safe calibrations. There is **no functioning communication with ECU**,
no Flash/Burn, no rusEFI memory page importer, and no claim of protocol
compatibility. It cannot be used to operate an engine.

## Run (desktop, Python 3.11+)

```bash
python -m pip install -e .
python -m power8gdi_configurator.app
```

## Model tests (do not require Qt)

```bash
python -m unittest discover -s tests -v
```

## GUI and complete regression suite

Run from this configurator directory in a Python virtual environment:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

GUI tests use real PyQt6 windows, table delegates and keyboard events. They
select Qt's `offscreen` platform by default and require no display server or
ECU. Run only these tests with `python -m pytest tests/gui -q`; set
`QT_QPA_PLATFORM` explicitly to override their headless default.

New, Open and Close offer Save / Discard / Cancel when the document has edits.
Cancelling Save As or a write failure retains the current document and stops
the requested replacement/close. Successful saves establish an undo checkpoint:
undo/redo back to that checkpoint clears the window's modified marker. Save As
changes the active filename only after the write succeeds. Cell text pending
in an editor is committed before file actions, including Ctrl+S.

Values requiring more than two decimal places retain their full float text in
the grid so entering and leaving a cell does not round its stored value.
The regression scope and remaining limits are recorded in
[`UI_OFFLINE_EDITOR_VALIDATION.md`](../docs/UI_OFFLINE_EDITOR_VALIDATION.md).

## Roadmap

- Read board-specific generated rusEFI `rusefi.ini` with verified offsets,
  endianness, page sizes, data types, scaling and signature.
- Implement binary TunerStudio communication in a dedicated transport module
  with CRC, page read/write and explicit flash commit guardrails.
- Export/import native `.msq` based on schema; include offline diffs and logs.
- Connect real ECU telemetry with recorder, safe status and bounded update rates.
- Bench-test over USB + CAN with firmware simulator, then validate on Power8GDI ECU.
- Implement EMU-Pro-style sensor, trigger, fuel, injection, ignition, boost,
  two-pump, DBW/EWG, knock, protection and ALS editors.

The project is isolated from hardware files. It will be split to a dedicated
GitHub repository once repository creation is available for the connected account.

## Experimental P4DM binary Map4D exchange

Python module `map4d_binary.py` reads/writes CRC-protected, versioned, little-
endian three-axis sample tables. It is a strict **offline interchange**, **not** a
native rusEFI TunerStudio page or write protocol. See
`../docs/MAP4D_P4DM_V1.md`.

The PyQt6 editor now supports a Z-layer selector for 4D maps. Editing and
undo/redo retain the layer identity even after changing the current view.

Use **Ctrl+F** to filter maps by name, description, axis or unit. Filtering
preserves the selected map, Z layer and undo history. Save/Discard/Cancel
protect unsaved edits when opening, replacing or closing a document.

The complete editor gate, including real headless Qt widgets and Python/C++
binary exchange, is `python -m pytest tests -v` after installing `.[dev]`.
A C++17 compiler is required; the model-only unittest command above does not
collect the Qt tests under `tests/gui/`.
