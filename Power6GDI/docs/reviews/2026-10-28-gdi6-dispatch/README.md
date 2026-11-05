# GDI6 dispatch guard — integration evidence, 2026-10-28

Full host suite: **PASS, 28 checks**, clean source revision
`d08daa8b309578f46bb4604f3adba12eba7fa6d4`. Machine-readable commands, timestamps,
outcomes and limitations are in `summary.json`; each named log accompanies it.

Implementation was developed in an isolated worktree as `0a6f51a` and integrated
as `16f6b78`. `13917e8` adds it to the common Linux/Windows host runner, updates
the six-cylinder firmware workstream and corrects the older safety header's
unsynchronized-ISR implication. The policy state is not atomic: all software
access requires a serialized owner or a shared platform critical section.

Root ran Python 3.12.10 and Clang 6.3.3+Asserts:

```text
python Power8GDI/tools/run_checks.py --suite host --cxx <clang++> --output <logs>
```

The runner compiles C++17 with `-O2 -Wall -Wextra -Werror -pedantic
-ffp-contract=off -UNDEBUG`. TEMP/TMP point to a writable task directory.
The new dispatch suite passes 16 scenario groups; configurator verification
passes 98 tests and 46 subtests. Strict costing passes 18 tests. No suite was
skipped or blocked. The independent reviewer separately compiled dispatch,
schedule admission and dual PT safety with `-O0 -g` and the same warning gates;
all three executables passed.

Review identified and corrected stale-standstill replay, configuration changes
across a normal stop, invalid-revision fault-time ordering, repeated-fault
recovery barriers and healthy-proof recovery starvation. Regressions distinguish
first-cause diagnostics from the latest unsafe observation. Atomic batches,
retained started reservations, both shared current paths, boost exclusion,
ticket replay, exact deadline boundaries, clock/ID overflow and default inhibit
are exercised in the source tests.

Final normalized SHA-256:

- Guard implementation: `37f6d92c40068bc433497e939d12a2cb8dc8557146dad0c10454391a2b8a90ad`.
- Scenario tests: `e10b2a7e0f369ef70b2d4052b05120366516917ef5bc58a9e59f360f21adfe9c`.

These results validate a host policy. They do not implement or qualify the
physical timer/GPIO adapter, atomic snapshot acquisition, ISR-to-owner event
handoff or independent hardware kill. A returned permit must never be cached
and later applied. Aggregate DI/HPFP boost capacity, driver current profiles,
microcode and electrical/thermal behavior remain unqualified. The generated
engine/guard qualification flags remain false and guard time remains zero.

The hardware snapshot in this validation is `403f73f`: D5604 silk correction
and the two WBO CAN logic routes. It still has 2097 unconnected items and
unresolved DRC/ERC work. Hardware reports and the PDF/Excel snapshot retain
their own explicit source revision and hashes. No engine or fabrication release
is implied by the host test result.
