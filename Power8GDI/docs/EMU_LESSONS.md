# Lessons from the EMU PRO firmware analysis

Status: design input for Power8GDI firmware. Updated 2026-10-21.

We study the ECUMASTER EMU PRO firmware (static offline analysis of versions 261.1/261.2, repository `emu-pro-firmware-research`, folder `rea/`) to find **weak spots that we must not repeat**. EMU PRO is not a reference design to copy. Every lesson below states the problem, the evidence, what Power8GDI does instead and the test that checks it.

Evidence marks from the analysis: **[F]** fact from code, **[?]** not established.

| # | EMU PRO problem | Evidence | Power8GDI decision | Check | Status |
|---|---|---|---|---|---|
| L1 | Ignition corrections, **knock retard included**, are applied only when the table owns the angle. During launch, anti-lag, idle, overrun and cranking the engine runs without knock and temperature retard. Launch and ALS are the hottest, highest-load moments. | [F] `rea/PSEUDOCODE_RU.md` §4, function `0x80043094`; `rea/REPORT_RU.md` §4.2 | Protective retard (knock, coolant, charge temperature; `AccumulatorLimits::protectiveIgnitionMask`) is applied to **every** angle owner. Only strategy offsets (limiters, traction, shift...) follow `correctionsApplyMask`. A protective source never adds advance to a non-table owner. | `ignitionKnockProtectionForEveryOwner` in `firmware/tests/test_arbitration.cpp` | fixed |
| L1b | Related, found in our own first version: if the ramp smooths the final angle, a knock retard that appears during a source change is delayed by the ramp. | own code review | Only the owner's base angle is rate limited; corrections are added after the ramp and act in the same cycle. | `ignitionKnockNotDelayedByRamp` | fixed |
| L2 | Lambda target: the nitrous ceiling is applied first, the "minimum" floor last. If the user sets the minimum leaner than the nitrous limit, the target goes **lean while nitrous is active**. | [F] `rea/PSEUDOCODE_RU.md` §5, function `0x80027008` | Floor first, ceiling last: on a conflict the richer limit wins. | `accumulatorRules` (floor 0.97, ceiling 0.85 → 0.85) | fixed by design |
| L3 | Cylinder cut tie-break is the hidden task number (gearbox > cranking > overrun > speed limiter > pit > launch > rolling > ALS > traction > overboost > rev limiter). The user cannot see why one cut pattern won. | [F] `rea/REPORT_RU.md` §4.2 | Same deterministic rule, but the order is the explicit registration order, documented in `ARBITRATION.md`, and every requester is published in `cutCandidateMask()` for logging. | `cylinderCutMaxWinsEarlierOnTie` | mitigated |
| L4 | In the table branch the ramp source pointer is not reset, so the ramp rate may come from the previous owner. | [?] `rea/PSEUDOCODE_RU.md` §4, not proven | The ramp always uses the rate of the currently selected owner. | `ignitionRamp` | by design |
| L5 | Angle source 6 "Ignition lock" exists in the configuration dictionary but nothing in the recovered code sets it. A user-visible option with no effect. | [F] not set by `0x80043094`; [?] 323 functions recovered only heuristically | Rule: no configuration option without a code path and a test that changes behaviour through it. | review rule | rule |
| L6 | float → int conversions of results into s16/s8 log channels most likely truncate toward zero. Truncation gives a biased log (e.g. −0.9° shows as 0°). | [?] indirect: `rea/REPORT_RU.md` §3 | Rule: every float → integer conversion for channels and outputs uses explicit rounding, and its unit tests include negative values. | to add with the first channel encoder | open |

## How to add a lesson

1. Link the evidence in `emu-pro-firmware-research` and mark it [F] or [?]. Do not record an [?] item as a fact.
2. Write what Power8GDI does instead.
3. Add a host test that fails with the EMU behaviour, or state why only a review rule is possible.
