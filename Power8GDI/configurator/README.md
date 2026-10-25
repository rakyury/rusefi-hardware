# R2 ECU Studio — separate desktop application

Offline Python/Qt calibration editor based on the existing project and the architecture of
[rakyury/racing_dash](https://github.com/rakyury/racing_dash): a versioned document
model, a responsive editor, UI independent of hardware transports, tests.

**Status: developer preview / OFFLINE EDITOR + DISPLAY SIMULATOR.** The map values are examples,
not engine-safe calibrations. There is **no functioning communication with ECU**,
no Flash/Burn, no rusEFI memory page importer, and no claim of protocol
compatibility. It cannot be used to operate an engine.

New projects use the explicit `sport-gdi6` target: 6 DI + optional 6 PI, two
HPFP, six ignition channels, one DBW, one EWG, one lambda, two knock inputs,
two CAN buses and required SENT/LIN. These are **project requirements**, not
hardware-discovered capabilities or evidence that the board is ready.

The package/command name `power8gdi_configurator` is retained for existing
installations. The user-facing client is independent of TunerStudio and INI
files. Its future transport and typed firmware metadata require an agreed,
verified ECU contract; selecting a map does not imply a firmware address.

## Existing projects and simulation

JSON format v3 stores the target profile explicitly. Opening v1/v2 preserves
all maps and their eight-cylinder identity as `legacy-power8gdi`. It does not
truncate channels or convert the project to six cylinders. A visible legacy
notice explains that saving writes v3; use **Save as** to retain the original.
Unknown profiles, conflicting counts and unknown top-level fields are rejected.
Hardware details absent from old files remain unspecified.

**Start simulator** produces bounded artificial display channels and an RPM
trace. It does not execute fuel/ignition strategies, decode CAN, connect to an
ECU or alter calibration. Units accompany every signal; the RPM trace retains
120 samples. Stop, successful New/Open, and Close clear simulated data. Legacy
projects cannot start this six-cylinder display fixture.

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

- Define typed parameters, units, revisions, writable ranges, device identity,
  capability discovery and schema migration jointly with firmware.
- Reuse racing_dash's native C VM and CAN stack through narrow adapters;
  retain shared PC/firmware behavior, with validated instruction budgets and
  permissions before ECU use. Do not introduce a parallel Python VM.
- Reuse applicable rusEFI console concepts after source review: discovery,
  connection lifecycle, diagnostics, logging and calibration tools. This is
  not a claim that its Java implementation has been ported into this Qt client.
- Implement project diff/merge, partial imports/exports, offline log playback,
  device selector, typed parameter tree and calibration assistants.
- Add real ECU telemetry only after verified framing and identity tests;
  memory writes, permanent save, output tests and firmware update follow their
  own protocol and bench acceptance tests.
- Implement sensor, trigger, modelled fuel, DI/PI, two-pump, ignition, boost,
  DBW/EWG, knock, protection, idle, overrun, launch, ALS and shift editors.

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
