# Independent LT3042 return review

Baseline extracted from immutable `git show 328b7ac`: SHA-256 `aa587f27ac9df7b35d8866f7716df9e7f06637fb603a7da4a8d693ec9f6cb392`.
Refilled candidate SHA-256: `638900cd40914d65b20f752ccf2698f53bb84e6ac96d56a0a211c24fb287576f`.
Native KiCad 9.0.9 API, read-only file loads; negative controls in disposable memory only.

## Results

Native full unconnected count **2087 → 2085**. Exactly two tracks added, no old tracks/vias removed or changed: all **2703** old UUIDs retain native geometric/net signatures.

Added UUIDs: `78a6f355-3aae-47bf-858d-d88a4032468a`, `e2fc5987-49e0-455d-984b-3706aa984fe1`.

| Native connectivity check | Baseline | Candidate |
|---|---|---|
| U5604.11 EP → existing via at 159,83 | true | true |
| U5604.8 GND → that via | false | true |
| C5662.2 Cout GND → that via | false | true |
| Existing EP via native In1 contact | true | true |
| C5661.2 Cin GND → its existing via at 156.988962,92.028729 | true | true |
| Existing Cin via native In1 contact | true | true |
| U5604.10 OUT → U5602.1 digital VDD | true | true |
| U5604.9 OUTS → C5662.1 | true | true |
| C5660.2 Cset GND → EP via | false | false |

EP via UUID: `d96e32b9-4b50-4783-8f84-acf18c3846ab`. Cin via UUID: `b3eaa996-42aa-4e2f-9c56-51bc6690c948`. The original .2 mm EP→via track `562b39b5-62bb-4bb0-9f16-0595de3997dc` is unchanged.

Power/sense preservation checked independently on the candidate: remove all three Kelvin tracks and detach OUTS9 on a disposable copy; OUT10 → digital VDD still has native BFS connectivity. Conservative 1 nm native polygon intersections of the Kelvin tracks with other B.Cu 3V3 tracks/vias/pads, minus Cout1 pad copper, remain **empty**. The new returns do not merge power and sense elsewhere.

## Corrected API interpretation and remaining work

An earlier exploratory classification incorrectly called the EP/Cin islands floating. `GetConnectedTracks` can return a via wrapped as PCB_TRACK, so `isinstance(item,PCB_VIA)` is not a reliable way to identify reachable vias. The checks above compare UUIDs to actual board vias and then use native IsConnectedOnLayer. Both old plane contacts existed before this change; no duplicate EP→via track was added.

Cset/SET needs a separate local Kelvin ground connection to Cout2. It is intentionally not connected through the common loaded EP return. Its pending status prevents treating this as a completed or validated regulator implementation. Full/scoped DRC and tokenized all-object/zone deltas remain the integration lead's separate checks; no hardware qualification is claimed.
