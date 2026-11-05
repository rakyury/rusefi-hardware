# Independent WBO MCU digital-supply review

Baseline bc8b1f55 PCB SHA-256: `e1887db8720d0945f611a9e5fe935d72f429a886bd382a77690af20472098e17`.
Candidate SHA-256: `5c1f064233a1a4ba51e6c8f209de365f30a4cd411869d71b7ece4dd3e51703e0`.
Native API: KiCad 9.0.9 (Docker kicad/kicad:9.0). Both boards loaded read-only and native connectivity rebuilt.

| Native check | Baseline | Candidate |
|---|---|---|
| Full unconnected count | 2089 | 2088 |
| U5602.1 VDD → C5612.1 BFS | false | true |
| C5612.2 GND → existing via at (180.15295,67.975) BFS | true | true |
| That via IsConnectedOnLayer(In1.Cu) | true | true |
| U5602.17 VDDIO2 → C5615.1 BFS | true | true |

All **2686** old track/via UUIDs retain their native parsed geometry/net signatures. This includes CAN RX/TX, VIO, RESET, U5610 GND and the three previous MCU/bypass ground returns. Exactly one new track UUID exists: `18dc4056-6782-451b-8216-2fc3edba0a23`.

The new track joins (176.35295,66.975) to (178.60295,66.975), F.Cu, width 0.25 mm, length 2.25 mm, WBO1_3V3. No new via is involved. The existing C5612 ground connection and native In1 contact remain intact. VDDIO2 already had its local capacitor connection, so it was not rerouted.

## Boundaries

BFS explicitly traverses native pads/tracks/vias of the endpoint net. Existing plane contact is verified separately using IsConnectedOnLayer, rather than inferred from labels. All-old-object tokenized/zone comparison and full/scoped DRC belong to the integration lead's separate verification. This report proves this local VDD branch, not completion of the entire 3V3 rail or hardware qualification.
