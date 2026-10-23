# GDI-02: source audit and independent-stage interface contract

Audit date: 2026-10-21. Repository snapshot:
`1ff4b732c121a33e1f15e169df428c90be87b3c7`.
Deliverable: an auditable interface requirement, validator and negative tests.
**Not a new schematic, routed board, approved BOM or production release.**

## Revision reconciliation

The checked-in `GDI-4ch/GDI-4ch.kicad_sch` and `.kicad_pcb` both carry revision
**d**, date **2023-05-14**. Both identify **U1 as MC33PT2001AE**. This confirms
their title metadata and device value agree; it does not establish that all
manufacturing exports were generated from these exact files.

There is a concrete mismatch in `GDI-4ch/gerber/rev. d/bom.csv`, line 55:
**U1 is MC33816**, while the current schematic/PCB value is **MC33PT2001AE**.
The BOM retains the same LCSC identifier C729087; that identifier does not resolve
the contradictory device names. Do not order using this BOM until the exact
approved variant, supplier item and assembly population are reconciled and the
exports regenerated together. Revision c DNP groups mentioned in the readme were
not assumed to apply to revision d.

The embedded library symbol is still named `chips:MC33816`. Its inherited PCB
metadata calls U1 pin 20 `VCC2P5`, and marks MISO/FLAG pins as inputs. This is a
symbol migration review item, not proof of a wiring defect. It can also weaken
ERC results if imported without reviewing pin types. No upstream file was edited.

## Manufacturer evidence and limits

The primary reference is NXP's [MC33PT2001 short datasheet, revision 10.1,
2023-02-15](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf), tables 1-2.
The AE variant is specified for VBOOST up to 72 V and lacks EOI measurement;
80 V belongs to H variants. Its pin 20 is VCC1P5, not VCC2P5. The pin table
describes FLAG0 as configurable I/O, rather than a fixed fault indication. These
facts require checking the exact selected variant and its programmed behavior.

NXP's [FRDMPT2001EVM page](https://www.nxp.com/design/design-center/development-boards-and-designs/FRDMPT2001EVM)
lists the evaluation guide, AN4849 and AN12336. Their official download links
redirected to NXP sign-in during this audit. The full device datasheet/safety
manual and matching microcode were not obtained. Polarity, thresholds, detailed
timing and diagnostic behavior were therefore not inferred from signal names,
old MC33816 documentation or another PT-family device.

## Interface requirement for the two proposed stages

The JSON contract defines independent logical nets for **A** and **B**. Each
stage supplies four injector commands and one HPFP command. These are design
requirements; all Power8GDI MCU pad assignments remain null/UNASSIGNED.

| Role | PT2001 package identity | Stage A / B requirement | Active / safe level |
|---|---|---|---|
| SPI chip select | CSB, pin 13 | Separate GDI_A_SPI_CSB / GDI_B_SPI_CSB | UNKNOWN |
| Reset | ResetB, pin 3 | Separate GDI_A_RESETB / GDI_B_RESETB | UNKNOWN |
| Drive enable | DrvEn, pin 2 | Separate GDI_A_DRVEN / GDI_B_DRVEN and disable domains | UNKNOWN |
| Diagnostic candidate | Flag0, pin 10 | Separate GDI_A_FLAG0 / GDI_B_FLAG0; programmed meaning unverified | UNKNOWN |
| Injector commands | Start1..4, pins 4..7 | Proposed four dedicated commands per stage | UNKNOWN |
| HPFP command | Package assignment UNKNOWN | Separate GDI_A_HPFP_CMD / GDI_B_HPFP_CMD | UNKNOWN |

Package identities above come from the NXP pin table; proposed actuator allocation
does not establish microcode mapping. HPFP must not be assigned a START pin simply
because its name appears plausible. The reference connector description says
control 6 can serve HPFP, but the entire conditioned input path and loaded
microcode were not traced and pinned here.

Only SCLK/MOSI/MISO are permitted as shared SPI wires in this logical contract.
This permission is conditional on later bus arbitration, timing, voltage and
MISO contention analysis. It is not validation of an electrical shared bus.
Engine-timed injector/pump commands must not be sent over CAN.

## Firmware reuse findings at the pinned snapshot

| Finding | Local evidence | Required Power8GDI work |
|---|---|---|
| Two CS definitions exist: PB2 and conditional PB3 | `firmware/main.cpp`, `spiCfg` | Confirm independent F7 CS pads and atomic per-device SPI transactions |
| Multi-chip reset/enable are shared PB5/PB4; per-instance setters do nothing | `pt2001impl.h`, `setResetB`/`setDriveEN`; `main.cpp` multi-chip branches | Replace shared control with separately owned stage controls and physical inhibit |
| Both instances read PB7 for FLAG0 | `pt2001impl.h`, `readFlag0` | Separate diagnostics and verify microcode meanings |
| Unexpected FLAG checking returns false | `pt2001impl.h`, `errorOnUnexpectedFlag` | Define and validate required diagnostic handling |
| Battery getter returns constant 12 | `pt2001impl.h`, `getVbatt` | Use validated supply measurements; no readiness claim from this getter |
| Faulted chips restart automatically in worker loop | `main.cpp`, `PtWorkerThread` | Integrate latched inhibition and deliberate re-arm after validated conditions |
| Defaults select one PT2001 and E92 feature flag | `efifeatures.h` | Pin build configuration and microcode; filenames alone do not identify behavior |

These are observations about the existing F1-oriented reference implementation,
not assignments for the Power8GDI F7. Initial PB4/PB5 low levels and later high
levels are observable source behavior, not independent manufacturer confirmation
of all electrical enable/reset semantics or power-up safety.

## Missing design and measurement evidence

| Area | Required evidence before integration/qualification |
|---|---|
| Device and exports | Resolve U1 mismatch; approve exact silicon variant and supplier; regenerate schematic, BOM, positions and Gerbers as one revision |
| Enable/reset path | Two independent physical inhibit paths; defined external pulls/inversions; MCU unpowered/boot/reset/halt behavior; fault timing and re-arm requirements |
| Boost circuits | Per-stage power budget and topology; selected inductor/MOSFET/diode/capacitor ratings; control stability, overshoot, discharge and fault-energy measurements |
| Current measurement | Shunt ratings/tolerance, Kelvin routing, return-current paths and gain/filter review; measured injector and HPFP current profiles |
| Driver paths | Gate-loop and bootstrap/decoupling layout, component ratings, clamp/snubber energy, short/open-load response and simultaneous-channel behavior |
| Timing/diagnostics | Pinned microcode/register images; START-to-output timing; independent HPFP phase; SPI loading; diagnostic coverage and measured disable latency |
| Interfaces and packaging | Exact F7 resources; harness/connector voltage and current ratings; thermal paths, copper/stackup and enclosure limits |
| Qualification | Fault injection, brownout/load transients, thermal steady state, EMC and engine validation with saved measurements |

The existing reference contains power-stage circuitry; it was not electrically
qualified by this audit. Power8GDI has not gained a dual-stage electrical
schematic through creation of this contract. ERC, DRC, simulations, firmware
flashing and physical tests were **NOT RUN** for this milestone.

## Provenance and licenses

`hardware/gdi/interface_contract.json` records exact Git blob IDs and SHA-256
digests for the seven inspected repository sources, plus the repository snapshot
and URLs. Local text digests normalize CRLF to LF so Windows checkout conversion
does not create false provenance failures. The validator verifies those local
digests; it does not fetch manufacturer documents during tests.

The public NXP PDF was retrieved as 652495 bytes. SHA-256:
`f3ef5a029ddd1458432397d2eb070724f34e5ec21f4ef71522426349d346abf1`.
NXP marks it copyright/all rights reserved. Only reference metadata and limited
factual pin information are recorded here; the PDF is not redistributed.

No applicable root or `GDI-4ch` license file or license statement was found for
the reviewed schematic, PCB, BOM or bespoke firmware files. Status is
**UNKNOWN_NO_APPLICABLE_LICENSE_FOUND**, not an inferred open-source license.
Apache-2.0 notices in ChibiOS configuration/linker files do not establish the
license of the whole design. Resolve reuse permission before copying design
assets into a product; this milestone references them in place.

## Validation and use

Python 3.8+; standard library only. From repository root:

```sh
python Power8GDI/hardware/gdi/validate_interface_contract.py
python -m unittest discover -s Power8GDI/hardware/gdi -p 'test_*.py' -v
python Power8GDI/hardware/gdi/validate_interface_contract.py --require-ready
```

The ordinary validator's PASS means audit consistency and local source hashes
match. It rejects shared enables/reset/CS/diagnostic/command nets, shared MCU pads,
duplicate disable domains, aliases hiding pin sharing, missing provenance,
unsubstantiated polarity, and unsupported readiness claims. Canonical proposed
MCU pads may be recorded for review but are not approved by this audit.

The final command deliberately exits **2** while this audit remains blocked;
it must not be substituted for the structural check in a passing test suite.
Invalid structure/provenance exits **1**. A default consistent audit exits **0**.
CI must include the `GDI-4ch` source directory, even when using sparse checkout.

Recorded on Windows / Python 3.12.10:

```text
GDI interface contract: PASS (audit consistency and local source hashes)
Hardware readiness: BLOCKED (7 recorded blockers; pins/polarities unresolved)
Ran 24 tests
OK
```

No upstream design, existing firmware, hardware connection or physical device
was changed. No push, PR or manufacturing approval is part of this milestone.
