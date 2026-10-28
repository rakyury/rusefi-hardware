# Independent reset-route connectivity review

Read-only verification on 2026-10-28, KiCad 9.0.9. Baseline is
`0e4c4268af444eb32dea0d345b211eb7728dc3d4`, candidate is `hardware/design/board/gdi6_candidate/Power8GDI_Review.kicad_pcb`, SHA256
`7e7872186f98b95cc92002db7e7e9ce3789c719f5df7182711846a7bdf729be0`.

After LoadBoard/BuildConnectivity, native GetUnconnectedCount(False) is
**2094 before → 2093 after**. These are complete connectivity counts, not
the number of entries in a potentially capped DRC report.

Native BFS using GetConnectedTracks/GetConnectedPads on actual net geometry:

| Endpoint pair | Before | After | Reachable objects after |
|---|---|---|---|
| U5612.1 → R5662.1, reset | false, source isolated | true | 2 pads + 7 segments |
| U5605.5 → C5618.1, VIO | true | true | 3 |
| C5618.2 → GND via (162.17795,69.805558) | true | true | 3 |
| U5605.2 → GND via (164.82795,62.765558) | true | true | 4 |
| U5602.21 → U5605.4, CAN RX | true | true | 8 |
| U5602.22 → U5605.1, CAN TX | true | true | 7 |

For both existing ground vias, native IsConnectedOnLayer(via, In1_Cu)
remains True before and after. This review does not substitute net labels
or absence of unconnected warnings for physical connectivity.

Parsed S-expression comparison keyed by UUID against git show 0e4c426:
**exactly seven added segments; zero removed or changed old objects**.
Non-UUID board nodes are identical. Thus all original pads, tracks, vias,
footprints, nets, mask/paste geometry and complete stored zone fills remain
identical, including the previously reviewed common GND plane and CAN/VIO
routes. No new vias or zone deltas occurred.

This reviewer did not rerun native DRC; root owns full/scoped DRC, its caps
and release decision. Connectivity proves only the requested local reset
branch and preservation checks above, not completion of the entire reset
network, board routing, supply distribution or hardware qualification.

No shared source or PCB files were edited by this verification. Only this
requested independent report was written.
