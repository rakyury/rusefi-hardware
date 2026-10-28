# GDI6 dispatch guard — host output-boundary policy

Status: implemented and exercised with synthetic host data, 2026-10-28.
This is not a qualified ECU firmware target or a GPIO/timer implementation.
The generated resource contract remains `ContractEnginePermission=false`,
`ContractGuardQualified=false`, `ContractGuardUs=0`. No hardware gate was enabled.

## Scope and invariant

`firmware/dual_gdi/gdi6_dispatch_guard.{h,cpp}` composes the existing
`admitDiSchedule` resource check with `DualPt2001Safety`. It owns a fixed array
of at most 32 reservations and uses no heap allocation. It accepts only the
`SportGdi6` profile; the historical eight-channel permits of the inner safety
class are never exposed by this API.

Each accepted event is either `Queued` or `Started`. Both states participate
in every subsequent admission check. The complete retained set is checked on
submit and again before an actual dispatch permit. A dispatch does not insert
another copy of its own queued event. The current-path reservation is the
half-open interval `[start, demagEnd + guardUs)`; boost-supply exclusion remains
`[start, boostEnd)` as defined by admission. DI1/DI2 and DI4/DI5 share current
paths; DI1/DI3 and DI4/DI6 share boost supplies. The two banks are independent
only with respect to these declared resources.

Started reservations are released only at or after the validated release
boundary. Stop, fault, cancellation, and acknowledge do not release them early,
even if a caller says the engine has stopped or has already asserted hardware
kill. A reservation means a permit was issued; it is deliberately retained if
the caller subsequently fails to deliver or complete the command.

## API and ownership

Construct `Gdi6DispatchGuard` once with an explicit positive
`DispatchGuardConfig::maxSnapshotAgeUs`. The qualification and age configuration
are immutable. An explicit synthetic `ScheduleQualification{true,true,10}` is
used only by the host tests; it supplies no injector timing qualification.

All methods, including getters, require one serialized owner. The object is
neither copyable nor movable. This class has no callback and no ISR entry point.

| Method | Result and meaning |
| --- | --- |
| `submit(events, count, snapshot, now)` | Validates the whole batch together with every retained event; allocates all tickets or none. A successful submit is not permission to drive outputs. |
| `dispatch(tickets, count, snapshot, now)` | Rechecks safety and full-set admission, then consumes all supplied queued tickets or none. Only this method can return events to execute. |
| `observe(snapshot, now)` | Updates safety/time/lifecycle, catches missed queued deadlines, and releases completed reservations. It returns no execution permit. |
| `stop(snapshot, now)` | Requires `runRequested=false`; cancels queued events and requests physical kill. Already started events remain reserved. |
| `acknowledgeStopped(snapshot, now)` | Explicit fault recovery using the existing stopped-and-healthy safety predicate; leaves the guard disarmed. It does not reset physical fault hardware. |
| `firstFault()` | First latched diagnostic, retained across secondary faults until successful acknowledgement. |

A caller may execute a returned dispatch batch only when all of these hold:

```cpp
auto permit = guard.dispatch(tickets, count, coherentSnapshot, capturedNow);
if (permit.status.requirePhysicalKill) {
    // The platform must immediately assert its independent physical kill path.
}
if (permit.status.accepted() && !permit.status.requirePhysicalKill &&
    permit.count == count) {
    // The platform may act only at the same exact event.start instant.
    // This placeholder is NOT an implemented timer/GPIO adapter.
}
```

`accepted()` on observe, stop, or acknowledge is not a START permit. Some
non-latching rejections (conflicting input batch, early call, invalid ticket)
leave `requirePhysicalKill=false` so that already running valid events need not
be interrupted. A rejected dispatch nevertheless returns `count=0` and no
execution events. The caller must check the complete predicate above.

Tickets are opaque, tied to their guard instance, and usable at most once.
IDs are unsigned 64-bit, allocated only after full-batch validation, never reset
on stop or recovery, and never wrapped. `initialTicketId` is a constructor-only
test seam for the exhaustion boundary; normal construction starts at one.
Zero is invalid. Exhaustion refuses subsequent submissions rather than recycling
IDs. Tickets must not be serialized, survive destruction/reboot, or remain in an
external queue while a guard is reconstructed at the same memory address.
The intended MCU integration uses one persistent static instance and discards
all old tickets at its lifetime boundary. Cross-instance pointers do not solve
address reuse after object destruction; that case is outside the lifetime contract.

## Time, coherent snapshots, and recovery

Every call receives absolute unwrapped monotonic microseconds, a coherent
`GdiSafetySnapshot`, its `capturedAtUs`, and a nonzero `configurationRevision`.
The caller is responsible for atomic/coherent capture and for each chip/rail
diagnostic's own freshness; stamping an old mixed set with a new timestamp is
not made safe by this wrapper.

Checks reject future capture times, samples older than the configured maximum,
backward `now`, backward capture times, non-GDI6 profiles, contradictory
standstill-plus-synchronization state, and absent revisions. Age subtraction is
performed only after checking capture <= now. Equal `now` and equal capture
times are allowed for simultaneous events sharing one coherent sample.
Clock watermarks are never reset by stop or acknowledgement. Even an invalid
configuration observation advances the monotonic `now` watermark before its
fault is recorded; a clock rollback retains the previous maximum.

Early dispatch returns `TooEarly` without consuming tickets. Permission is
issued only for `now == start`; pulse times are never shifted. On any observation,
an unstarted event with `start < now` is a latched `MissedDispatch`: all pending
events are cancelled and physical kill is required. The owner must call this
API at deadlines; it cannot detect time passing while it is not being called.

The session locks the injector profile, rail topology, pump/sensor configuration
masks, and external configuration revision. The revision must change for any
PT current/phase calibration or related timing configuration change. Such
configuration cannot change across a normal stop until all started reservations
are released and a healthy confirmed standstill snapshot has been observed
with `capturedAtUs > last armed observation now`. For normal stop, first observe
that boundary with the old revision, then supply the new configuration on a
subsequent call. Stopping without standstill evidence keeps the lock.

A latched runtime/safety fault cancels pending events and invokes the existing
software fault latch. Recovery requires a new healthy confirmed stopped sample,
no run request, no synchronization, and capture strictly after the recovery
barrier. Each new fault advances that barrier to the latest monotonic observation
time without replacing the first-cause diagnostic. While already latched,
running, unconfirmed, or unhealthy observations advance the barrier too. A healthy
stopped observation does not advance it: `observe(stopped T, T)` followed by
`acknowledgeStopped` with that same fresh coherent copy can recover. An unhealthy
acknowledge or incompatible configuration while a reservation remains advances
the barrier too. Rejection solely because a healthy proof predates the barrier
does not move it, so lagged fresh samples can eventually qualify. Old but still
age-valid standstill samples cannot clear faults or unlock configuration.

Acknowledgement while started reservations remain is allowed only with the same
session configuration and preserves those reservations. When no started event
remains, a healthy acknowledge may establish the boundary for a subsequent new
configuration. Successful acknowledgement stays disarmed; a later fresh run
request is needed. It never restores cancelled tickets.

## Failure and atomicity semantics

Runtime/time/profile/configuration/safety failures latch, preserve the first
cause, cancel queued events, retain started events, and require physical kill.
Invalid proposed event batches, resource conflicts, capacity exhaustion, ID
exhaustion, bad tickets, and early dispatches are rejected without partially
accepting/consuming the proposed batch. Routine lifecycle maintenance may still
release already expired started entries before a rejected proposal is evaluated;
this is not partial acceptance. The fixed capacity includes started entries.

Cause ordering is deterministic: observation/clock validity, existing latch,
missed queued deadline, session configuration, then inner safety; batch validity,
admission, and ticket checks follow. A missed deadline can therefore be the first
diagnostic even when that same sample reports another safety failure. All such
cases still request physical kill. Later observations do not replace the first
latched cause; `RecoveryDenied` describes an unsuccessful acknowledgement while
`firstFault()` continues to expose the original cause.

## Validation and limits

`firmware/tests/test_gdi6_dispatch_guard.cpp` contains 16 scenario groups covering
queued/in-flight collisions across batches, shared paths and boost supplies,
independent/simultaneous banks, exact release boundaries, atomic batch rejection,
late/early dispatch, stop/rearm, fault recovery, all safety prerequisites,
configuration changes, capture/clock replay, repeated faults, integer/ID overflow,
capacity, cross-instance/replayed tickets, and default inhibition.

Host command from repository root (C++17; test executable outside source tree):

```text
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -pedantic -UNDEBUG \
  Power8GDI/firmware/dual_gdi/dual_pt2001_safety.cpp \
  Power8GDI/firmware/dual_gdi/gdi6_schedule_admission.cpp \
  Power8GDI/firmware/dual_gdi/gdi6_dispatch_guard.cpp \
  Power8GDI/firmware/tests/test_gdi6_dispatch_guard.cpp -o gdi6-dispatch-test
./gdi6-dispatch-test
```

The guard has no timer/GPIO/DRVEN/START hardware effects. The gap between a returned
permit and the physical START remains the MCU adapter's responsibility. A host
check does not close an interrupt-time safety race; independent hardware kill,
serialized dispatch, exact timer timing, and proper failure handling are still
required. Do not cache or defer a permit, use this object from an ISR, or equate a
software kill request with verified de-energization.

HPFP overlap, aggregate power/boost recharge capacity, electrical injector phase
timings, current ramps, demagnetization qualification, MCU scheduling/WCET and
timer wrap capture, F7 firmware linking, physical fault reset, and engine/thermal/
EMC validation remain out of scope and unqualified. This guard alone must not
enable operation on the engine.
