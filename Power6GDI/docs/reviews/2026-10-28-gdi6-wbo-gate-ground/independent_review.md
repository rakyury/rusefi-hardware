# Independent U5610 logic-ground review

Candidate SHA-256: `3a6f881bd42b702a6e085e7eddefbcd569296583262431f3ccb02c25484b4f9b`.
Baseline: checked-in PCB at `671da0b`, SHA `7e7872186f98b95cc92002db7e7e9ce3789c719f5df7182711846a7bdf729be0`.
Native API: KiCad 9.0.9, Docker kicad/kicad:9.0. Read-only loads; negative control was in memory and never saved.

## Result

- Native full unconnected count: **2093 → 2092**.
- Exactly two added track/via UUIDs: `186bf83f-c141-404b-b9d2-157cfde1ecee`, `80b566d3-9e53-42f4-a2ae-aaad7354d7f6`.
- Every old track/via UUID retains its native parsed geometric/net signature.
- U5610.3 GND at (178.8625,82.55) reaches via (178.8625,81.8) by native GetConnectedTracks/GetConnectedPads BFS.
- Native IsConnectedOnLayer(via,B.Cu) and IsConnectedOnLayer(via,In1.Cu) both true.
- The via lies in the single continuous filled outline of In1 GND zone `424ddee3-374b-41a8-85b8-c40338f4eff0`.
- Negative control: remove that zone on the disposable in-memory board, rebuild connectivity; native IsConnectedOnLayer(via,In1.Cu) becomes false. Thus contact is not inferred only from matching net names or polygon containment.

Six native module regression tests passed, covering idempotence, pad→via BFS and native plane contact/control, original track/via preservation, supply/device/position contracts, partial or altered route rejection, an opposite-layer obstacle, and a same-net drill obstacle. Obstacle rejection leaves the board unchanged.

## Boundaries

This report proves the local logic-ground connection only. It does not claim a mixed-zone BFS (the relevant SWIG vector binding is unavailable), completion of the U5610 supply/decoupling loop, whole-board DRC clearance, or hardware qualification. Full/scoped DRC and tokenized board/zone deltas are the integration lead's separate checks. Existing CAN/VIO/reset copper signatures are unchanged as part of the all-old-track/via comparison.
