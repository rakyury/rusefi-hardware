# Power8GDI / R2 GDI 8 — engineering status

Updated 2026-10-23. A connected hierarchical schematic now replaces the earlier
connector-only sketch. PCB integration and routing are in progress.

## Agreed configuration

- STM32F767IIT6, two PT2001 banks, 8 GDI and 2 HPFP valve channels.
- 24 low sides: 8 high-impedance PI, 4 VVT, 8 AUX and 4 service.
- 8 passive-coil ignition stages with dwell windows, current comparators and
  latched inhibit. Exact G42 M240i/B58 coil characteristics remain open.
- 4 motor bridges: DBW, EWG and two spares.
- 2 onboard LSU4.9 controllers, 2 knock channels, 4 provisional SENT inputs,
  2 LIN buses, 2 classic CAN buses, USB and SD.
- Zero onboard EGT; separate module and protocol still to be selected.
- Four 34-contact headers (136 contacts), differing from Huge connector sizes.

The authoritative scope is [target_profile.json](../hardware/target_profile.json)
and [the scope record](SCOPE_2026_10_23_HUGE_GDI8.md). Huge is a capability
reference; pin compatibility is not claimed.

## Circuit progress

| Block | Implemented | Open work |
|---|---|---|
| GDI | Reference-derived stages, protected feeds and permission gates | PT2001 electrical/shutdown evidence, loaded START6 microcode; qualification links remain DNP |
| Ignition | 9 sheets, 146 components, independent actual-pin audit and standalone ERC | Coil profile, transient/thermal limits, external supply relay, physical returns |
| WBO | 6 sheets, 148 components, source-topology audit | Root regeneration, physical layout and local-controller/sensor tests |
| Motors | 7 sheets, 106 components, four bridges, two protected feeds | Root integration, aggregate current, regeneration and thermal tests |
| Logic power | 2 sheets, 32 components, LM76003 and sequenced TPS62130A | Replace both old supplies; capacitor DC bias, loop response and thermal tests |
| MCU/interfaces | Resource draft, low sides, protected inputs, SENT/LIN/CAN and knock | Actual firmware timing/DMA, sensor profiles and fault tests |

The WBO generator previously merged distinct amplifier + and − nets. Commit
`d697c0a` fixes the labels and adds an independent comparison of actual source
connectivity partitions. Earlier WBO exports and their passing checks are
superseded; deliberate merged-net mutations are now rejected.

## Verification and PCB

The last full root run before the new power/motor integration was checkpoint
`d320637`: 50 sheets, 1165 components and 42 ERC findings. Its symbol mismatch
fix awaits regeneration. That run does not validate subsequent modules or the
corrected WBO exports. The next report must include their actual root-netlist
hash. [review_validation.json](../hardware/design/review_validation.json)
records command results and scope; schematic-only validation excludes PCB DRC.

The earlier 631-component board and DRC reports are historical. The current
layout must match the new root netlist and account for ignition spacing, GDI
loops, current returns and sensitive analog regions. No current-board zero-DRC
or manufacturing claim is made.

Injector, pump, coil and motor models remain unspecified. Final current ratings,
dwell and boost profiles cannot be derived from channel counts. Connector RMS
current, aggregate returns and repetitive ignition pulses need qualification;
a dielectric withstand test alone does not establish it.

Startup/brownout, dummy-load faults, thermal, EMC, mechanical fit and engine
operation remain unmeasured. See [deliverable gates](DELIVERABLE_GATE.md).
