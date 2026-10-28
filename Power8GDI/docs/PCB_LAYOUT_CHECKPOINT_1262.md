# Physical PCB checkpoint: 1262 components

This checkpoint matches the 1262-component, 3951-pin root netlist, SHA256 `d7fb0ddc652c735b1617ddce309dcb4ca93b4729c80044e7e9be3e5e50e74ae7`. Board: `hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pcb`, 245 x 165 mm, four copper layers. It supersedes the earlier 1236-part artifact; it is not fully routed or ready for fabrication.

Both GDI donor banks retain their mapped copper, with previously documented omitted outer buses and dangling-tail cleanup. Eight ignition cells have 32 local connections. Compact 5 V and 3.3 V buck placement is reserved before general packing. Local buck and WBO routing contributions are deliberately not included in this checkpoint. Most new inter-module connections, current-return distribution, Kelvin connections and thermal review remain unfinished.

The full pad-to-net verification passed: 1262 components, 3951 assignments, 35 DNP components, zero errors. Nine board regression checks passed. Sixty discovered PT2001 switching nets have explicit 0.6 mm clearance rules; no discovered coverage gaps remain. Battery aliases PTA/PTB_+Batt_filtered use 0.3 mm. This audit does not cover all motor/charge-pump or buck switching nets. Ignition uses a provisional 2.5 mm target; package/connector pulse qualification remains open. No severity, clearance or width exceptions were introduced.

After applying the rules and refilling zones, KiCad 9.0.9 reported 938 violations: 504 clearance, 199 track width, 172 silk overlap, 49 silk over copper, 12 dangling vias and 2 dangling tracks. Clearance and width reports hit internal category caps; these counts are not complete totals. The separate 499-item unconnected report is also capped. The full connectivity engine residual is **2602 connections**. There are 2602 track/via objects; this equal number is coincidental and is not a routing percentage.

The saved DRC provenance hashes the PCB, project and explicit rules. Those hashes were checked again after preview exports. Front/back SVG and PNG show the actual saved copper and placements without a drawing-sheet overlay; the back preview uses the same coordinates as the front, not a mirrored assembly view. This placement predates expansion of the common HV obstacle policy; DRC therefore records its remaining conflicts rather than claiming retroactive clearance compliance.

Verification commands from the repository root (Python commands run inside `kicad/kicad:9.0`, mounted at `/work`):

```text
python3 Power8GDI/hardware/design/board/verify_board.py Power8GDI/hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pcb Power8GDI/hardware/design/core.net
python3 -m unittest discover -s Power8GDI/hardware/design/board/tests -v
python3 Power8GDI/hardware/design/board/run_drc.py Power8GDI/hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pcb --output Power8GDI/hardware/design/board/layout_candidate/drc.json
python3 Power8GDI/hardware/design/board/summarize_drc.py Power8GDI/hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pcb Power8GDI/hardware/design/board/layout_candidate/drc.json Power8GDI/hardware/design/board/layout_candidate/net_coverage.json
python3 Power8GDI/hardware/design/board/audit_gdi_voltage_domains.py Power8GDI/hardware/design/core.net Power8GDI/hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pro --output Power8GDI/hardware/design/board/layout_candidate/voltage_domain_audit.json
```

The DRC command intentionally exits nonzero. Remaining work is routing and electrical/physical review, not report suppression.
