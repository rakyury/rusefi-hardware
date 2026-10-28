# racing_dash CAN importer provenance

User-requested reuse of their existing project, not a new CAN implementation.

- Repository: `rakyury/racing_dash` (private).
- Inspected local checkout: `C:/Projects/racing_dash`.
- Revision: `2c66c178083ae4bd0f2f0afe928ecd799af6347c`.
- Source: [`configurator_qt/src/core/can_import.py`](https://github.com/rakyury/racing_dash/blob/2c66c178083ae4bd0f2f0afe928ecd799af6347c/configurator_qt/src/core/can_import.py).
- Source Git blob: `c1d0c2e0b3ee8d7a562c0467526bd95949311685`.
- Source on-disk SHA-256 (CRLF): `678d150744c0f4ad81cdc156237c3ca459ad1678eb234ba4177fbe00674bebf3`.
- Verified source blob against that revision with `git ls-tree` and
  `git hash-object` before copying. No source images, user calibrations,
  dashboard assets, compiled vendor drivers or credentials are included.

The source's module documentation is retained. No new third-party license is
invented here; this record attributes the selected source and local changes.

## Deliberate local changes

1. Zero DBC scale stays `0/1`, instead of silently becoming `1/1`.
2. Nonfinite/out-of-range scales are rejected. A numerator too large with a
   denominator of one cannot loop indefinitely. Approximation beyond the
   specified relative tolerance is reported instead of silently changing scale.
3. Fractional/nonfinite/out-of-int32 DBC offsets are explicitly reported as
   skipped, rather than truncated. Fixed-point decimal metadata is a future
   schema task; it is not guessed from a floating-point number.
4. Preserve DBC extended-ID flags, reject inconsistent IDs and keep the
   standard/extended multiplexor selectors separate for equal numeric IDs.
5. Unsupported/orphan signal syntax generates visible warnings. Correct the
   stale header comment: the inspected CANX implementation handles Compound
   selectors; it does not blanket-skip them.

The thin `can_preview.py` adapter bounds file size/count, rejects XML entity
declarations, checks preview ID addressing, exposes warnings and returns
immutable display rows. It does not call upstream `apply_import`, instantiate
CAN transports, transmit or decode frames, or install ECU configuration.
CANX's existing tolerant number defaults/clamps remain explicitly warned.

The configured `bus=None` keeps CANX's bus choice; DBC defaults to CAN1.
Explicit choices preserve racing_dash's convention: 0=CAN1, 1=CAN2, 2=both.
These are source model values, not assigned ECU protocol field numbers.

Regression tests cover standard/extended identity, mux separation, CANX child
addressing/bus selection, zero/large/imprecise scales, fractional offsets,
unsupported syntax, XML declarations and size/bus bounds.
