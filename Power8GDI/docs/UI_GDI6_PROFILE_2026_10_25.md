# UI-05: Sport GDI6 profile and display simulation

2026-10-25. Scope: desktop client only. Hardware and ECU behavior are untested.

The new default is `sport-gdi6`, revision `2026-10-25`: six cylinders, 6 DI,
optional 6 PI, two HPFP, six ignition, one DBW, one EWG, one lambda, two knock,
two CAN buses, SENT and LIN. The project profile is a static description of
the approved target; it is not a response from a connected ECU. Existing
module/import and directory names remain compatible with the earlier project.

JSON format v3 explicitly records profile and legacy import provenance. v1/v2
files are opened as `legacy-power8gdi`, retaining all table data and eight
cylinders. Unknown or inconsistent profiles are rejected. There is no automatic
six-cylinder conversion and no asserted hardware capability absent from the
old document. The UI labels legacy projects and warns that saving produces v3;
Save as retains the source file. New/Open preserve existing unsaved-edit guards.

The simulator is a deterministic **display fixture**, not a plant model or
firmware emulator. It produces six typed channels with units: RPM, MAP absolute
pressure, lambda, DI rail pressure, DBW and EWG position. No map influences
these artificial signals. No adapter, serial connection or CAN transmission
is created. A bounded 120-sample RPM trace accompanies read-only numeric data.
New/Open/Close stop and clear the fixture after the operation succeeds; failed
or cancelled operations retain the active document/session. Legacy projects
cannot start the six-cylinder fixture.

Validation includes profile/count rejection, v1/v2 round-trip preservation,
simulator determinism/bounds/disconnect, real Qt window checks for legacy
labels, save-as migration, unchanged maps during simulation and session cleanup.
The existing map, file lifecycle, 4D editor and Python/C++ P4DM tests also run.
These checks do not verify ECU communication, bytecode execution, electrical
outputs or engine calibration.

Profile/simulator checkpoint: **89 tests + 37 subtests passed** on 2026-10-25.
At this checkpoint the separate CAN preview test module was excluded because
its integration is delivered in the next commit. Same-agent QA review checked
profile identity, migration preservation, Qt lifecycle and bounded simulation;
an independent integration review is still required before merge.

Reproduction on the inspected Windows host, from `Power8GDI/configurator`:

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:TEMP='C:/Users/User/Documents/Codex/2026-10-25/x20/work/client-test-tmp'
$env:TMP=$env:TEMP
& 'C:/Users/User/AppData/Local/Programs/Python/Python312/python.exe' -m pytest tests -q --basetemp='C:/Users/User/Documents/Codex/2026-10-25/x20/work/client-pytest-tmp'
```

`tests/gui` uses Qt offscreen windows. P4DM parity requires a C++17 compiler;
the inspected host uses Swift LLVM clang++ 6.3.3. The custom temporary location
avoids this host's inaccessible default pytest temporary directory. A normal
virtual environment can instead use the README command without path overrides.
