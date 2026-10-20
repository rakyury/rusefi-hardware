# HW-01 resource audit — 2026-10-21

The current draft passes input-structure validation and fails qualification. No new pins have been assigned. STM32F767xx is a candidate family; the exact order code, package and silicon revision remain unspecified.

`hardware/audit_resources.py` reads the GPIO CSV, connector CSV and `hardware/resource_contract.json`. The checked-in `hardware/resource_audit_report.json` is a reproducible snapshot with SHA-256 hashes of all three inputs normalized to UTF-8/LF without BOM, source revisions and locators, requirement coverage, resource findings and explicit unverified checks. Normalization keeps the report portable across Git line-ending settings.

| Result | Current draft |
|---|---:|
| GPIO rows / distinct assigned pins | 78 / 46 |
| Required functions in the audit scope | 104 |
| Missing from GPIO allocation | 26 |
| Explicitly UNASSIGNED | 32 |
| Confirmed pin/channel/EXTI/reservation collisions | 0 |
| Interface conflicts conditional on mode choice | 5 |
| Missing qualification evidence groups | 13 |

After integrating upstream `6abecaa`, 26 former omissions (24 PI/VVT/AUX/low-side commands and CAM3/4) have explicit UNASSIGNED rows. No new pin was assigned. The remaining 26 absent rows cover eight digital inputs, FLEX_FREQ and 17 analog/temperature inputs. The 32 explicit gaps also include SENT3/4, LIN2 TX/RX and CAN2 TX/RX. Optional/provisioned channels remain open until a reviewed scope decision. A connector net is a requirement, not a claim that it needs one direct MCU pad; external drivers and frontends still need allocation and capacity review. Dual wideband interfaces are a separate unresolved evidence item.

The upstream `resource_audit.py` is retained as a narrower logical allocation checker. Its `complete` flag concerns that subset only. This report's `audit_resources.py` includes connector requirements and explicitly blocks qualification even when logical rows are filled.

## Additional findings from primary sources

These are conditional route conflicts, not assertions that an undecided peripheral is already enabled:

- SDMMC1 D0 on PC8 overlaps EWG_PWM even in one-bit mode; four-bit mode also overlaps HPFP1 on PC9.
- The reviewed SDMMC2 route overlaps SPI2 MISO/MOSI on PB14/PB15 and LIN1_RX on PD6 (clock).
- OTG_HS embedded-PHY DM/DP overlaps GDI SPI2 PB14/PB15; this does not describe an external ULPI route.
- PA15 PTB_CS overlaps JTAG JTDI. Debug mode and reset handoff need review.
- IGN1 PC13 needs buffer/load review: its special output restrictions include 3 mA switch capacity, 2 MHz/30 pF limits and current-source restrictions. This alone does not prove the proposed buffered ignition interface invalid.

Source: ST [DS11532 Rev 9](https://www.st.com/resource/en/datasheet/stm32f767zi.pdf), Table 11 pp. 75, 78–81 and footnote 2 p. 85. The contract records narrow pin facts, not a complete AF/package database.

DBW_PWM and EWG_PWM share TIM3's counter/prescaler/auto-reload despite using different channels. Compatible frequency/mode requirements have not been established. EXTI port aliases are checked separately from GPIO duplicates. Source: ST [RM0410 Rev 5](https://www.st.com/resource/en/reference_manual/rm0410-stm32f76xxx-and-stm32f77xxx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf), §§7.2.3–7.2.6 and 26.4.14–26.4.19. TIM5/TIM6 reservations come from the project's F7 resource plan, not ST-defined exclusive assignments.

## Meaning of the gate

- `structure_status=pass` means the supplied draft records are parseable and structurally consistent. It does not qualify pin functions or approve routing.
- `collision` means an explicit allocation conflicts with another allocation, a project timer reservation, or a selected interface route.
- `conditional_conflict` means an undecided interface would overlap the current GPIO draft if that reviewed route were selected.
- `unverified_*` and `qualification_evidence` preserve missing AF numbers, package pads, DMA controller/stream/channel/priority, ADC routes, interrupts, electrical limits, clock/power/reset/debug and shutdown evidence. GPIO_TIMED, TRIGGER_INPUT and CAM_INPUT do not identify a timer/EXTI backend.
- `release_eligible=false` is intentional for this audit stage. There is no signoff acceptance mechanism. Editing statuses to `verified`, choosing a mode, or inserting an approval flag cannot open the gate. A later reviewed qualification workflow must examine actual evidence.

Reserved interface pin facts also cover SWD, HSE/LSE and OTG_FS. Absence of a listed overlap means only that; VBUS, USB/SD clock domains, supplies, VCAP, NRST, BOOT0, oscillator design and firmware reset transitions remain unverified. No DMA routes were supplied, so this stage cannot assert that DMA is conflict-free. KiCad CLI was not found on PATH; ERC/DRC were not run. The existing connector-only schematic and board outline are not altered by this audit.

## Reproduce

From the repository root (Python 3.12; standard library only):

```powershell
py -3.12 Power8GDI/hardware/audit_resources.py --gate structure --output Power8GDI/hardware/resource_audit_report.json
py -3.12 -m unittest discover -s Power8GDI/hardware/tests -v
py -3.12 Power8GDI/hardware/audit_resources.py
```

The first command exits 0. The tests verify actual failure cases including duplicate pads, timer-channel aliases, EXTI aliases, timer reservations, mode-dependent conflicts, malformed input and attempts to bypass qualification. The last command deliberately exits 2 because the default is the release gate; this is the expected current result, not an audit-tool crash.

Primary-source provenance is transparent: the ST datasheet was viewed as the publisher PDF; RM0410 sections were read through the publisher's indexed text because the full PDF exceeded browser fetch limits. No source-download hash is claimed. Canonical local-input hashes are included in the generated report. No circuit, MCU firmware, connector electrical or physical test qualification is implied.
