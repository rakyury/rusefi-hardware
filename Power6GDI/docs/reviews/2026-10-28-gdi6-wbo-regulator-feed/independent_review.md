# Independent LT3042 power-feed and Kelvin review

Immutable baseline: PCB extracted with `git show 9c013c8`, SHA-256 `5c1f064233a1a4ba51e6c8f209de365f30a4cd411869d71b7ece4dd3e51703e0`.
Refilled candidate SHA-256: `aa587f27ac9df7b35d8866f7716df9e7f06637fb603a7da4a8d693ec9f6cb392`.
Native KiCad 9.0.9 API, read-only file loads. Negative control only in memory.

## Connectivity and topology

- Native full unconnected count: **2088 → 2087**.
- Native pad/track/via BFS U5604.10 (OUT) → U5602.1 (digital VDD): **false → true**.
- U5604.9 (OUTS) → C5662.1: **true** in candidate.
- Delete all three new Kelvin tracks and detach OUTS pad9 from 3V3 on a disposable copy: OUT10 → digital VDD remains **true**. Power delivery does not use the sense branch.
- Conservative native polygon intersection test: each Kelvin trace converted with 1 nm ERROR_OUTSIDE, intersected with all other B.Cu 3V3 power tracks/vias/pads (excluding OUTS and the Cout contact itself); subtract C5662.1 copper polygon generated with 1 nm ERROR_INSIDE. **No residual intersection outside the Cout pad**.

## Preservation

Exactly **16 tracks + 1 via** added. Exactly one old track removed: `356b15fb-c05f-4989-8f07-b7abc7518ed0`, the .2 mm B.Cu shortcut from OUTS9 (163.15,85.5) to OUT10 (163.15,86). All other **2686** old track/via UUIDs preserve their native geometry/net signatures, including CAN, VIO, reset and prior ground returns.

The following previous ground returns retain both native pad→via BFS and native IsConnectedOnLayer(via,In1.Cu), before and after refill:

| Pad | Existing via mm | Baseline BFS/In1 | Candidate BFS/In1 |
|---|---|---|---|
| C5612.2 | 180.15295,67.975 | true/true | true/true |
| U5602.16 | 169.37795,61.25 | true/true | true/true |
| U5602.32 | 176.22795,68.85 | true/true | true/true |
| U5610.3 | 178.8625,81.8 | true/true | true/true |
| C5618.2 | 162.17795,69.805558 | true/true | true/true |
| U5605.2 | 164.82795,62.765558 | true/true | true/true |

## Limits

The new signal via requires a GND antipad. Exact filled-polygon delta and full/scoped DRC are separate integration checks; this independent review verifies preservation of the native contacts above after refill. No complete regulator-operation claim: Cout/Cset/IC ground return completion remains pending. This is a verified power-feed topology, not hardware, thermal, stability or EMC qualification.
