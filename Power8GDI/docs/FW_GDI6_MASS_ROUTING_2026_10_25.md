# GDI6: DI/PI mass routing and explicit driver profile

Date: 2026-10-25. Base: `2d0e66e`. Profile ID: `sport-gdi6`.

This is tested, controller-independent C++ policy. It is not a flashable MCU
target, an injector current driver, a rail-pressure controller, or a completed
engine scheduler. The historical `Power8GDI/` path remains to preserve the
existing development history. New mass-domain code uses namespace `power6gdi`.

## Implemented path

`firmware/fuel/allocation_gdi6.{h,cpp}` takes six individually corrected masses
in **mg per cylinder per 720 crank degrees**, a DI fraction, a per-cylinder fuel
cut, separate DI/PI capacities, and the hydraulic configuration.

1. Reject non-six-cylinder imported configurations, missing/invalid rail and
   pump assignments, non-finite/negative inputs and split fuel with no PI fitted.
2. Return an all-zero inhibited plan when fuel permission is absent.
3. Apply cylinder fuel cut to both DI and PI before generating an event request.
4. Split the total into separate binary32 DI/PI masses. Compare the actual
   representable output doses against independently supplied injector/window
   capacities. No implicit redistribution or clipping occurs.
5. Sum each cylinder's final DI mass into its assigned **hydraulic** HP rail.
   PI never contributes to the HPFP consumption feed-forward. A driver bank is
   not assumed to identify a hydraulic rail.
6. For a shared HP rail, allocate DI consumption in proportion to the capacities
   of its one or two configured pumps. For independent rails, both rail/pump
   pairs are required; spare capacity on one cannot conceal starvation of the
   other. Any capacity violation rejects the whole cycle with every mass/event
   zero and an explicit reason.

Example: cylinder totals 10/20/30/40/50/60 mg with 50% DI give 105 mg DI and
105 mg PI. Shared pumps with capacities 400/200 mg per engine cycle receive
consumption feed-forward masses 70/35 mg and fractions 17.5%/17.5%. The erroneous
`cylinder[0] * 6` would give only 30 mg DI. This implementation sums all six.

The feed-forward percentage is a fraction of calibrated delivery capacity. It
is **not** HPFP valve duty or pulse duration. Zero injector consumption does not
mean the pressure controller can stop maintaining rail pressure. The existing
dual-HPFP supervisor remains separately tested; no unreviewed mg-to-valve bridge
has been introduced.

## Explicit PT2001 board profile

`dual_gdi/dual_pt2001_safety.*` now requires an explicit `SportGdi6` or
`LegacyGdi8` profile. The default is unconfigured and cannot enable outputs.
The six-cylinder profile permits only logical cylinders 1-6; slots 7/8 remain
false. Both PT2001 chips and their diagnostic prerequisites remain mandatory.
A profile change while armed latches a configuration fault and requires the
existing deliberate stopped-engine recovery path.

These are logical cylinder permits, not raw START pin numbers. The hardware
workstream's proposed GDI6 mapping is PTA START1-3 for cylinders1-3, PTB START1-3
for cylinders4-6, and START6 on each chip for its pump. The physical adapter and
generated netlist must verify this separately. It must not use the first six
slots of an old four-plus-four physical output map.

## Verification

Focused command from repository root:

```text
python Power8GDI/firmware/tests/run_fuel_gdi6_tests.py
```

Clang 21.1.6, x86_64 Windows, C++17, `-O2 -Wall -Wextra -Werror -pedantic
-ffp-contract=off -UNDEBUG`. The new mass suite and complete PT2001 gate suite
pass. Cases include 320 cut/split combinations, all256 imported cylinder counts,
all256 driver profile values, shared/independent rails, one/two pumps, late
cylinder capacity failures, invalid numeric values, float aggregate overflow,
no partial results, zero-dose/no-event, and the 70mg*0.1f capacity boundary.

The broader portable runner additionally builds and passes Map4D, P4DM blob,
dual-HPFP allocator and dual-HPFP safety suites. The full host runner is **not
green** at this base: its old schematic-vs-CSV check finds DIN5-8 versus MOTOR3/4
labels, and the system Python3.10 lacks pytest for the configurator suite.
Those are recorded failures, not silently excluded or counted as firmware passes.

## Integration still required

- A pinned rusEFI core and actual F7 board target with reviewed GPIO/timer/DMA.
- Immutable coherent runtime configuration, fresh capabilities and sensor data.
- Separate DI and PI timing/electrical models; actual start/end windows and
  multiple injections, min-dose and long-injection policies.
- Apply the accepted plan atomically to the event scheduler; repeat safety
  checks at actual event execution. A computed `EventRequired` is not a GPIO
  permission. Rejecting a plan must cancel queued events according to the
  scheduler contract, not merely leave the previous plan active.
- Rail-pressure feedback plus pump/lobe scheduling and the electrical driver.
- Calibration of actual mass capacities and all physical fault/timing tests.

## MAP-04 review

The existing Map4D/P4DM scalar table remains compatible with six cylinders:
three inputs, scalar output, `[Z][Y][X]` storage, bounded 4096 cells and32bins/axis.
Both existing C++ suites pass. It is not yet a wire-schema or live ECU feature.
Its current evaluator validates every cell per lookup; budget or move immutable
validation to publication before using it in a real-time control path. This
change does not alter its numeric/codec semantics or claim MCU timing results.
