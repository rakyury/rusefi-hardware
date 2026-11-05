# Independent WBO VIO/ground connectivity review

Reviewed read-only on 2026-10-28 against baseline
`e47f09301d6e3de56d04d71d60d73330b8800069`.
Candidate: root worktree
`output/gdi6_wbo_vio_20261028/Power8GDI_Review.kicad_pcb`.
Candidate SHA256:
`75e98a2a132238da55b954a4b55d0bde57f14ed8334183e136645a9238173bdf`.
All KiCad experiments used a read-only repository mount; no PCB was saved.

## Parsed delta

Comparing parsed S-expressions keyed by UUID against the baseline:

- Exactly **four new segments and two new vias**.
- Zero removed objects and **zero changed old objects**.
- All non-UUID board nodes are identical.
- All footprints, pads, original copper, nets and zone objects are identical.
  In particular, this refill produced **no stored zone-fill delta**: the new
  GND vias join existing same-net fill, unlike prior signal-via antipads.
- Both previously accepted CAN TX/RX routes retain their original objects
  and geometry.

## Native pad/track/via connectivity

After `LoadBoard` and `BuildConnectivity`, traversed the native
`GetConnectedTracks` / `GetConnectedPads` adjacency, filtering each traversal
to its actual net. This is geometric connectivity, not matching net labels.

| Check | Native reachability | Component size |
|---|---|---|
| U5605.5 → C5618.1, WBO1_3V3 | true | 2 pads + 1 track |
| C5618.2 → via (162.17795,69.805558), GND | true | 1 pad + 1 track + 1 via |
| U5605.2 → via (164.82795,62.765558), GND | true | 1 pad + 2 tracks + 1 via |
| U5602.21 → U5605.4, WBO1_CAN_RX | true | 2 pads + 5 tracks + 1 via |
| U5602.22 → U5605.1, WBO1_CAN_TX | true | 2 pads + 4 tracks + 1 via |

## Native ground-plane contact, including negative control

The two added GND vias are UUIDs
`064b456a-fd3f-4663-8c54-dd889a4f5212` and
`d0e23836-f7e4-4f0d-91e2-c1bfa8f6d907`.

For **each** via, native
`board.GetConnectivity().IsConnectedOnLayer(via, pcbnew.In1_Cu)` returned
**True**, and the B.Cu check also returned **True**. This establishes an
actual connectivity-engine contact on In1, not just polygon containment.

Performed a negative control on a disposable in-memory load of the same
candidate: removed only GND zone
`424ddee3-374b-41a8-85b8-c40338f4eff0`, called `BuildConnectivity` again,
then repeated both In1 checks. Both returned **False**. No changed PCB was
written. Thus the observed native In1 contacts depend on that GND zone.

Its stored In1 filled polygon set has **one outline**, and both via positions
are within that same outline (index 0). Together with the native contacts and
negative control, this confirms the two local pad→via paths join the same
continuous GND fill. The proof is not based solely on labels or `Contains`.

API boundary: a direct mixed pad/track/zone BFS through `GetConnectedItems`
could not be invoked: KiCad 9.0.9 Python lacks the required
`std::vector<KICAD_T>` typemap, while `CN_CONNECTIVITY_ALGO` is opaque SWIG.
Accordingly this report does **not** claim that such a mixed-object BFS was
executed. Instead it reports the native layer-contact checks, their negative
control and the single-filled-outline identity explicitly.

## Implementation and builder integration

Reviewed final `route_wbo_vio.py`: guards device/value, endpoint net/layer/
position, exact existing branch signatures and partial branches. It preflights
all three branches before `board.Add`, checks actual all-layer copper and
voltage domains, holes including same-net drill obstacles, and effective
front/back mask openings for vias. Accepted earlier branches enter the
obstacle index for subsequent ones. No placement or electrical changes were
found in the implementation or actual candidate.

Builder calls it after functional placement and accepted CAN routing, before
zone fill. The newly added UUIDs are included in `local_copper_ids` before
`remove_dangling`, so cleanup cannot silently discard these intended branches.

No substantive defect in this bounded implementation/result was found.
Global WBO1_3V3 and +5V_CORE distribution, C5613 VCC decoupling, thermal/current
qualification and unrelated unrouted nets remain outside this result.
The integrator separately owns full/scoped native DRC and its truncation
limits; this reviewer did not rerun those checks or infer connectivity from
absence in a capped unconnected report.
