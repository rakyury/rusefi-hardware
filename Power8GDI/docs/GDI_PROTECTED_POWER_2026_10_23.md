# GDI protected feeds and hardware permission, 2026-10-23

This increment adds three connected KiCad sheets and 42 fitted components to the
existing two PT2001 stages. Eight DI channels and two HPFP channels are retained.
It is an engineering circuit, not an energized or engine-qualified ECU.

## Implemented circuit and integration contract

| Sheet | Root instance UUID | Function |
| --- | --- | --- |
| `gdi/protection_a.kicad_sch` | See `protection_manifest.json` | Separate bank A battery protection |
| `gdi/protection_b.kicad_sch` | See `protection_manifest.json` | Separate bank B battery protection |
| `gdi/permission.kicad_sch` | See `protection_manifest.json` | Independent bank request AND hardware permission |

Root integration joins `HARNESS_VBAT_GDI_A_1` and `_A_2` to
`VBAT_GDI_A_FUSED`, and corresponding B contacts to `VBAT_GDI_B_FUSED`.
They must arrive through externally fused feeds; these sheets do not contain a
precision electronic current limiter or an on-board fuse. The two protected
outputs already use the stage names `VBAT_GDI_A` and `VBAT_GDI_B`. They must never
be aliased directly to the raw harness nodes.

Both power controllers take their permission through a 1k series resistor and
10k pull-down from existing `HW_ACTUATOR_ENABLE`. No extra MCU pins are required.
Software must keep all actuator commands and both per-bank DRVEN requests low,
arm the hardware latch to establish bank power, wait for valid supplies, then
reset/program/read back the PT devices before requesting actuation. A hardware
fault removes feed permission. Residual boost energy means feed removal is not
a substitute for the separate driver inhibit path.

`PTA_DRVEN` and `PTB_DRVEN` remain independent MCU requests. U5101 outputs
`PTA_DRVEN_GATED` and `PTB_DRVEN_GATED` only when the corresponding request AND
hardware permission are high. Each request, each gated output and each actual
PT DRVEN pin has its own pull-down. The existing isolation links R299/R399 now
receive the gated signals. Their documented DNP qualification hold remains.

Stage A START6/pin9 now uses `HPFP1`; stage B START6/pin9 uses `HPFP2`.
START5 remains unallocated. This implements the previously traced command
mapping, rather than leaving the MCU pump signals disconnected. Integration
must update `interfaces_aux/gdi_output_contract.json` pump `start_net` values to
match these names. Pump HS5/LS6, fitted drain-sense links R216/R316 and DNP
alternative links R218/R318 are unchanged. Source topology equivalence tests
still pass. `pcb_handoff.json` is regenerated to include the renamed START6 nets.

## Part selection and limits

Each LM74800-Q1 controls two common-drain IPD90N10S4-06 MOSFETs. The first source
is input; the second source is output. The controller's CAP capacitor returns to
the common-drain VS node. OV uses 140k/10k, 0.1% resistors. The calculated rising
cutoff is 18.465V nominal; a deliberately conservative static bound is
17.864V to 19.075V including comparator, divider, switch resistance and 200nA
leakage. This leaves static margin below the existing 5V regulator's 20V normal
input ceiling. It does not bound transient output overshoot.

The new LM74800 land pattern follows the current TI DRR0012E drawing: 1.3x2.5mm
exposed pad, 0.5mm pin pitch. **The exposed pad floats electrically.** Do not use
the stock 1.5mm exposed-pad footprint or join its thermal area/vias to GND. The
project footprint has no vias; its stencil aperture choice still needs assembly
review. Controller pin13 is explicitly no-connect.

SMCJ33CA is the provisional bidirectional input TVS. Its energy coordination,
exact manufacturer/automotive grade, hot clamping and fuse choice remain open;
there is no ISO pulse compliance claim. The 22nF HGATE slew capacitor and series
1k resistor provide a startup-ramp candidate. Its interaction with the retained
GDI bulk capacitors, hot MOSFET SOA and repetitive power cycling must be checked
with actual injector/pump loads. Gate-source fallback resistors are 1M; their
load is included in the unresolved startup calculation. Neither the MOSFET's
catalogue current nor this layout establishes board current rating.

## Evidence and unresolved PT enable dependency

- [TI LM7480-Q1 SNOSD95C](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf): pin table p3, electrical limits pp5-6, slew network p15, common-drain application p19; current package addendum DRR0012E drawing4224874/C.
- [TI SN74LVC2G08-Q1 SCES557E](https://www.ti.com/lit/ds/symlink/sn74lvc2g08-q1.pdf): DCU8 pin table and AND function; Ioff at VCC=0.
- [Infineon IPD90N10S4-06 Rev1.1](https://www.infineon.com/assets/row/public/documents/10/49/infineon-ipd90n10s4-06-datasheet-en.pdf): pin1 gate, pin2/tab drain, pin3 source; 100V VDS and +/-20V VGS. MOSFET voltage rating is not surge qualification.
- [NXP MC33PT2001 short datasheet Rev10.1](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf): actual PT pin names and DRVEN weak pull-down. This public document does not provide the complete enable threshold/timing/configured shutdown evidence.

Official full PT datasheet and safety-manual URLs were checked again and were
not publicly retrievable. No MC33816/PT2000 truth table or third-party copy of
an NDA-marked document was substituted. R299/R399 remain DNP specifically until
the exact PT2001 electrical thresholds, configured pump shutdown and partial-power
behavior are confirmed. This is an explicit unresolved interface; it must not be
reported as an operational GDI output. The loaded START6 mask/image still needs
proof that optional injector6 code cannot also select the pump pulse.

## Reproduction and checks

From the repository root:

```text
python Power8GDI/hardware/design/gdi/generate.py
python Power8GDI/hardware/design/gdi/build_protection.py
python Power8GDI/hardware/design/gdi/verify.py --kicad
```

The last command uses pinned KiCad9.0.9 and exports all five GDI leaves. Run
`check_protection_footprints.py` inside that image to load all 42 real footprints;
the resulting JSON records footprint hashes/pads and checks floating-EP geometry.

New tests inspect actual exported netlists, including deliberately reversed
MOSFET-source, wrongly grounded EP, misplaced charge-pump capacitor and bypassed
hardware permission mutations. They supplement the original 11 source-topology,
pin, DNP, provenance and pump-command tests. Standalone ERC keeps expected external
power/permission findings visible: each protection leaf has two power-source
errors and one dangling cross-sheet label; the gate has two power-source errors,
one externally driven-input error and two cross-sheet-label warnings. These are
not suppressed or called a clean integrated ERC result.

PCB routing, dynamic/thermal simulation, dummy-load tests, EMC and engine tests
are not performed by this circuit increment. Actual fuse current, boost setpoint,
injector peak/hold currents and pump profiles remain unspecified because the
actuator models have not been selected.
