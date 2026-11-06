# Independent WBO logic-ground review

Baseline d35e9ab PCB SHA-256: `3a6f881bd42b702a6e085e7eddefbcd569296583262431f3ccb02c25484b4f9b`.
Candidate SHA-256: `e1887db8720d0945f611a9e5fe935d72f429a886bd382a77690af20472098e17`.
Native API: KiCad 9.0.9, Docker kicad/kicad:9.0. Both files loaded read-only; negative control performed only in memory.

## Results

Native full unconnected count **2092 → 2089**. All **2680** old track/via UUIDs retain their native geometric/net signatures, including previously accepted CAN RX/TX, VIO, RESET and U5610 logic-ground routes. Exactly six new objects exist: three tracks and three vias.

| Endpoint | Pad coordinate mm | Via coordinate mm | Track | Native pad→via BFS | Native F.Cu/In1 contact |
|---|---|---|---|---|---|
| C5612.2 | 180.15295,66.975 | 180.15295,67.975 | F.Cu, 0.25 mm × 1 mm | true | true/true |
| U5602.16 | 169.37795,60 | 169.37795,61.25 | F.Cu, 0.25 mm × 1.25 mm | true | true/true |
| U5602.32 | 174.97795,68.35 | 176.22795,68.85 | F.Cu, 0.25 mm × 1.346291 mm | true | true/true |

All vias are through .65/.30 mm. All three centers lie within the same single continuous filled outline of In1 GND zone `424ddee3-374b-41a8-85b8-c40338f4eff0`. Removing only that zone from the disposable in-memory candidate and rebuilding connectivity changes native IsConnectedOnLayer(via,In1.Cu) to **false for all three vias**. This verifies actual plane-dependent contacts, rather than relying solely on net names or polygon containment.

Added UUIDs:
- `10a3df89-dd97-44a2-841b-367f8ed6591e`
- `1888d374-54c4-4978-93da-76891a0eeeef`
- `3def2cdf-d2f4-4a84-85d5-ba42e84c340b`
- `898b0168-8d34-4c5a-a7f7-e03b0eab4e99`
- `c9fc37d7-8eef-4988-b96d-19376c98373e`
- `fe819242-3abb-43a3-929a-9a80ebfd7494`

## Limits

C5612 is identified as a nearby 3V3 bypass, without asserting exclusive MCU decoupling ownership. Native BFS here traverses pads/tracks/vias; plane connectivity uses IsConnectedOnLayer plus the zone-removal negative control and single-outline check, not a claimed mixed-zone BFS. All-old-object tokenized comparison, zone polygon deltas and full/scoped DRC are separate integration-lead checks; this report's preservation result is specifically native track/via geometry/net signatures. No complete-board or hardware qualification claim.
