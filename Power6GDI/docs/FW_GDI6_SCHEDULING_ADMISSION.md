# GDI6 current-path scheduling admission

The six-channel hardware shares a high-side/current measurement path between
DI1/DI2 and DI4/DI5. A START falling edge does not demonstrate coil current has
decayed. `firmware/dual_gdi/gdi6_schedule_admission.*` therefore checks the entire
boost, pickup, hold, demagnetization and qualified guard reservation. It also
enforces the conservative one-boost-phase-per-PT-bank policy.

The resource map is generated from
`hardware/design/gdi/scheduling_contract.json`, with a normalized source hash.
The common host runner rejects a stale header. Contract mutations test missing
or duplicate channels, omitted demagnetization, unsupported concurrency and
invalid qualification. C++ fixtures cover phase overlaps, exact boundaries,
unsorted input, repeated pulses, independent banks, malformed events and integer
overflow. Fixture timings are synthetic and must never become injector settings.

This is an offline admission primitive, not an MCU scheduler or PT2001 driver.
It performs no GPIO writes, microcode loading, pulse shifting or clipping. The
caller must supply the complete event set, including already executing events,
in one absolute monotonic time domain and repeat validation at dispatch. Cyclic
angles/timer wrapping must be resolved before calling. Pump concurrency, aggregate
power, injection windows and synchronization require additional gates.

The committed hardware contract has engine permission false and no qualified
guard. Default construction consequently rejects every schedule. Test-only
qualification explicitly supplied in fixtures does not approve engine operation.
