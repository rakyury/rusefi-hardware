# Power8GDI Configurator — separate desktop application

Offline Python/Qt calibration editor inspired by the architecture of
[rakyury/racing_dash](https://github.com/rakyury/racing_dash): a versioned document
model, a responsive editor, UI independent of hardware transports, tests.

**Status: 0.1 developer preview / OFFLINE ONLY.** The map values are examples,
not engine-safe calibrations. There is **no functioning communication with ECU**,
no Flash/Burn, no rusEFI memory page importer, and no claim of protocol
compatibility. It cannot be used to operate an engine.

## Run (desktop, Python 3.11+)

```bash
python -m pip install -e .
python -m power8gdi_configurator.app
```

## Unit tests (do not require Qt)

```bash
python -m unittest discover -s tests -v
```

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
