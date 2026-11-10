# Independent output and GDI mapping review

Reviewed 2026-10-21. This report adds evidence and checks only; it does not change parent-owned output, core, GDI or PCB generators.

## TLE9104SH output domain

Read-only review of the integrated `hardware/design/outputs/build_outputs.py` against [Infineon TLE9104SH Rev1.31](https://www.infineon.com/assets/row/public/documents/10/49/infineon-tle9104sh-datasheet-en.pdf) confirms IN1/2/3/4 pins3/18/4/17, OUT1/2/3/4 pins1/20/10/11, RESN13, EN14, VIO15 and VDD16. The input commands are active low; the LVC14 inversion correctly makes a high MCU command active. EN must be high and the SPI OUT_EN bit set. All four grounds plus the internally floating exposed pad are externally grounded as recommended.

Six reset inputs can source 600 microamperes maximum in the specified operating conditions. Including the declared buffer's 10 microampere Ioff assumption and 1% 1 kOhm pull-down gives 0.6161 V, below the TLE 1 V low-input limit. This calculation does not prove every rail-ramp state. The firmware must hold reset low at least 10 microseconds after VDD stabilizes, and restart that sequence after either rail fault. The builder documents this requirement. No pin-number or active-level defect was found in this scope. Full output current, clamp energy, thermal performance, supply sequencing and shared hardware-enable fanout remain qualification gates.

## GDI source-to-output mapping

The hardware tree pins `ext/libfirmware` to commit `78cec274c6eec850d394c21770dc21267aa27d43`. The default upstream head read during this review was `dffa2426620039f6711def5a794c41c5dd03194f`, dated2026-09-26. Both reviewed microcode files have identical git blobs at these two revisions. Hashes, immutable URLs and the revision-matched schematic SHA256 are recorded in `interfaces_aux/gdi_output_contract.json`.

The following table combines the [rusEFI ch1 microcode](https://github.com/rusefi/libfirmware/blob/78cec274c6eec850d394c21770dc21267aa27d43/pt2001/project/rusefi/MicrocodeCh1/ch1.psc), [ch2 pump microcode](https://github.com/rusefi/libfirmware/blob/78cec274c6eec850d394c21770dc21267aa27d43/pt2001/project/rusefi/MicrocodeCh2/ch2.psc) and the exported GDI4-derived graph. `PTx` means PTA or PTB; add4 to bankB injector numbers.

| Logical channel per bank | START pin/net | Microcode switches | Positive output | Negative output |
|---|---|---|---|---|
| DI1 | pin4 / DI1 | hs1,hs2,ls1 | PTx_H1 | PTx_L1 |
| DI2 | pin5 / DI2 | hs1,hs2,ls2 | PTx_H1 | PTx_L2 |
| DI3 | pin6 / DI3 | hs3,hs4,ls3 | PTx_H3 | PTx_L3 |
| DI4 | pin7 / DI4 | hs3,hs4,ls4 | PTx_H3 | PTx_L4 |
| HPFP | pin9 / PTx_START6 | hs5,ls6 | PTx_H5PUMP | PTx_L6PUMP |

Pin8 START5 is not the pump request in this reviewed source. Pump drain sensing goes through sourceR37, copied to R216/R316, which is fitted. Alternate sourceR41, copied to R218/R318, is DNP. Both selector states must be preserved. G_LS6 drives both optional injector6 and pump MOSFET gates in the inherited topology; source microcode also contains an optional injector6 START6 branch. Consequently the raw source mapping does not prove safe arbitration: the selected channel configuration/start masks and the actually assembled/downloaded code must be validated together. Do not connect an extra injector6 load or infer simultaneous channel capability from this table.

The [rusEFI driver](https://github.com/rusefi/libfirmware/blob/78cec274c6eec850d394c21770dc21267aa27d43/pt2001/src/pt2001.cpp) treats low reset and drive-enable commands as shutdown and enables them only through initialization. This is corroborating software evidence, not a replacement for PT2001 electrical/polarity and fault-state specifications. The physical enable boundary R299/R399 remains DNP. CS pin13, reset pin3, FLAG0 pin10, DRVEN pin2 and SPI pins14/15/16 are checked against the actual exports; no guessed signal pin is used.

`check_gdi_mapping.py` verifies both banks' eight injection and two pump paths, source selector populations, unused START5, supply/control pins and DNP enable isolation. A deliberate START6 net mutation must fail. `--netlist <root.xml>` checks the same constraints on an integrated KiCad XML netlist. `--require-ready` exits2 after structural checks because unresolved gates remain. This validates electrical node identities, not assembled microcode equivalence or physical operation.

## Supply and land-pattern limits

VBAT_GDI_A/B each require a distinct fused/protected high-current feed. The core buck's protected logic feed is not a GDI supply. This review does not invent a fuse/current value, TVS clamp, trace width or reverse-protection MOSFET without the load profile and full PT2001 absolute limits. A dedicated reverse-battery/surge-disconnect front end per bank is a reasonable next circuit; device voltage margin, fuse coordination, startup inrush, ripple and boost energy must be calculated before adopting a specific part/value. Those missing circuits are visible boundaries, not hidden by aliases.

The primary NXP [SOT1510-1 /98ASA00237D](https://www.nxp.com/docs/en/package-information/98ASA00237D.pdf) contains actual reflow footprint guidelines on pages5–7. Its package summary confirms 0.5 mm pitch and4.9 mm exposed pad. During this review the local download endpoint returned404; browser text exposed the document but not readable copper drawing dimensions. Search-index stencil dimensions are not copper-pad evidence. Therefore no approval of a0.30 mm copper width or clearance-rule exception is issued here. The inherited ADV7611-labelled5 mm source footprint remains a blocker until the actual manufacturer copper drawing is visually checked and the geometry regenerated.

## Integrated auxiliary-test API

`python hardware/design/interfaces_aux/test_aux.py` verifies the four committed standalone XML exports. `python hardware/design/interfaces_aux/test_aux.py --netlist hardware/design/core.net` runs the same twelve assertions against the integrated XML. There is no automatic net-alias allowance: renamed integration nets must be explicitly reviewed. The old775-component root export correctly fails because it lacks all auxiliary components. A fresh integrated export is required for a passing integrated result.
