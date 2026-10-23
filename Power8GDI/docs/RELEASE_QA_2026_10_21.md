# QA-07 integration review, 2026-10-21

Reviewed integration snapshot: `ff5bcde` on `codex/power8gdi-qa-20261021`,
followed by the fixes and regression tests recorded in this commit.
Scope: offline editor lifecycle/storage, P4DM exchange, HPFP policy source,
host/CAD validation orchestration, CI triggers and audit qualification gates.
This is a bounded software review, not hardware or manufacturing signoff.

## Confirmed defects and fixes

1. **Invalid imported metadata could replace the active document before raising
   an exception.** Numeric `x_label`, `y_label`, `value_unit` or `z_label` passed
   model validation. `open_project()` installed the incoming project and cleared
   history, then search-tree construction raised `TypeError`. A five-case real Qt
   regression produced **4 failed, 1 passed** before the fix. Both table models
   now validate all text metadata before installation. Rejected imports retain
   the previous project, path, values, undo history and dirty state.
2. **Save consumed an existing `.tmp` sidecar and leaked its temporary file on
   replacement failure.** The deterministic `target.name + '.tmp'` path could
   overwrite unrelated recovery data and then move it away. Two new regressions
   failed before the fix. Save now creates its own unique sibling temporary file,
   closes it before atomic replacement, and removes only that temporary file in
   cleanup. Injected replacement failure preserves the existing destination.
   This does not add concurrent-document conflict resolution or power-loss
   durability guarantees.
3. **Reference-source-only changes did not trigger the provenance checks in
   CI.** The workflow's push and pull-request path filters omitted `GDI-4ch/**`,
   although the GDI validator hashes those files. Both filters now include that
   dependency. Workflow execution on GitHub remains **NOT RUN**.

## Verification actually performed in this QA checkout

Environment: Windows, existing `qa-env` Python runtime, offscreen Qt, local Clang
host compiler. `PYTHONPATH=Power8GDI/configurator`; `QT_QPA_PLATFORM=offscreen`.
Commands run from repository root with that environment's Python executable:

```text
python -m pytest Power8GDI/configurator/tests/gui Power8GDI/configurator/tests/test_project.py -q
54 passed in 2.52s

python -m pytest Power8GDI/configurator/tests/test_map4d.py Power8GDI/configurator/tests/test_map4d_binary.py Power8GDI/configurator/tests/test_map4d_parity.py -q
24 passed, 21 subtests passed in 4.89s
```

The GUI coverage includes actual delegate editing, Save/Save As, unsaved
Save/Discard/Cancel flows, failure handling, cross-map/layer undo and redo, clean
checkpoints and search. The parity tests compile and execute the production C++
reader against Python bytes, including boundaries, invalid CRC-valid inputs,
non-finite queries and binary32 edge cases. No parity defect was found within
this tested coverage.

Four audit CLI commands were executed through subprocesses and their return
codes asserted, rather than inferred from printed messages:

| Command | Observed result |
|---|---|
| `hardware/audit_resources.py --gate structure` | Exit 0; structure pass; `release_eligible=false` |
| `hardware/audit_resources.py` | Exit 2; qualification remains blocked |
| `hardware/gdi/validate_interface_contract.py` | Exit 0; audit consistency/local hashes pass; hardware BLOCKED |
| `hardware/gdi/validate_interface_contract.py --require-ready` | Exit 2; hardware BLOCKED |

Paths in this table are relative to `Power8GDI/`. The MCU report still records
52 missing required functions, 6 explicitly unassigned functions, 5 conditional
conflicts and 13 missing qualification evidence items. The GDI gate retains 7
explicit blockers. A passing structural test is therefore not a release pass.

`git diff --check` passed. The integration lead owns the aggregate host and CAD
runs; they were not rerun here or represented as independent QA executions.

## Source review observations and boundaries

- The HPFP wrapper starts disarmed, retains the first fault, requires a valid
  explicit re-arm, and validates again before returning enabled demand. The
  pure allocator remains separate. This QA pass reviewed that source; prior
  host evidence is in `FW_03_SAFETY_SUPERVISOR.md`. It is not connected to physical
  inhibit lines, supplies or the MCU scheduler.
- `run_checks.py` records subprocess status, command, log and source revision;
  it blocks missing compiler/Qt dependencies and only runs CAD contract tests
  after fresh CAD generation. Its PASS is an offline suite outcome, and its
  summary explicitly excludes hardware qualification.
- CI configuration was inspected, but no hosted Linux/Windows runner result is
  claimed. Source-path coverage was corrected; runner provisioning and remote
  execution remain to be verified by an actual workflow run.
- The later remote `dual_pt2001_safety` additions and their merge are outside
  snapshot `ff5bcde` and **outside this QA report**. They require their separate
  review and the integration lead's final aggregate validation.

## Outstanding release blockers

The F7 core/target, exact MCU/package and pinmux, independent PT2001 electrical
integration, GDI BOM/device mismatch, polarity/microcode and licensing evidence,
vendor connector geometry and mating remain unresolved as documented by their
respective workstreams. No ERC/DRC, complete firmware target build, MCU-in-loop,
physical fault injection, thermal/EMC, engine operation or manufacturing review
was performed by this QA milestone. Concept CAD and host tests do not clear any
of those gates. No hardware access, flashing, upstream design edit, push or PR
was performed.
