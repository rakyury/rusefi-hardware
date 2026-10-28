# Connected electrical review — 2026-10-21

This checkpoint replaces the connector-only electrical placeholder as the
working design. Open `hardware/design/Power8GDI_Core.kicad_pro` and
`hardware/design/board/review/Power8GDI_Review.kicad_pcb`. The older placeholder
files and original upstream boards remain unchanged.

**Engineering candidate: full schematic completion and full routing are still
outstanding. Manufacturing and engine use remain blocked.**

## Integrated artifacts

| Domain | Connected implementation |
| --- | --- |
| Core | STM32F767IIT6, all 176 pads accounted for, oscillator, reset/debug, 3V3 regulator, CAN1/LIN1, eight smart-coil buffers |
| Logic input | 19-part fused-12V input candidate with reverse diode, TVS and LM5164-Q1 buck |
| GDI | Two 134-part reference-derived PT2001 stages with independent feeds and local 5V regulator candidates; output/enable qualification incomplete |
| Inputs | 171 parts on eight sheets: 17 analog channels, four Hall cam channels, four SENT channels and differential VR crank |
| Hardware permission | 33 parts: watchdog, brownout/kill supervisor, latched re-arm and eight ignition gates |
| Motors | Two 25-part DRV8871 candidates with gated PWM/direction, separate feeds and current-limit resistors; motor selection absent |
| Harness | Four TE34 connector symbols and drawing-derived four-row footprints, explicit alias table |

The hierarchy has 20 sheets and 631 components, including 34 DNP parts. The
actual XML contains 1996 component-pin assignments. DNP flags are propagated
to the physical board and checked after reloading it. Eight ignition series
links and both GDI DRVEN boundary links remain DNP.

The PCB has a provisional 245x165mm outline, four copper layers, 2598 track/via
objects and 15 zones. It contains transferred, endpoint-audited GDI subdomain
copper and short core decoupling routes. The 254 new IO/safety/motor parts
have provisional backside placement in the quieter lower board region.
That placement is packed for collision review; it is **not** a completed
functional layout with reviewed decoupling loops, thermal spreading or routing.

## Verification and its limits

`python Power8GDI/hardware/design/run_review.py` regenerates all new source-owned
leaves, exports actual XML, checks hierarchy boundaries, rebuilds the board,
compares every pad/value/DNP flag, and runs unsuppressed KiCad ERC/DRC. It uses
KiCad 9.0.9 in an image pinned by SHA256. Full commands and outputs are in
`hardware/design/review_validation.json`; `--release` returns nonzero.

- 11 core/integration tests include deliberate ignition bypass, motor permission
  bypass, wrong VR mode, direct MCU/harness connection, lost DNP and connector
  swap mutations. Six board-contract, ten safety, eleven GDI and twelve resource
  tests cover their separate contracts. Power and motor checks evaluate actual
  exported connections and bounded arithmetic, not physical behavior.
- Root ERC: 117 findings (104 dangling global labels and 13 undriven power pins).
  This includes unfinished harness boundaries and passive power-source paths.
  No PWR_FLAG, severity downgrade or ERC exclusion was added to hide them.
- PCB DRC: 752 violations and 499 unconnected items. Of these violations,
  511 concern copper clearance; most involve inherited GDI routes around 0.15mm
  against the provisional 0.20mm minimum. Other findings include silk/text,
  drill and dangling track/via issues. There are zero reported cross-net shorts
  in this checkpoint. That does not establish electrical safety or full routing.
- A placement defect initially put new backside pads on existing through vias.
  Six shorts were reproduced. Placement now treats vias and backside copper
  as obstacles, uses stable sorting, and the fresh DRC no longer reports them.
- All 631 physical components, 1996 assigned pins and 34 DNP flags match the
  integrated export. This is connectivity consistency, not timing, EMC or
  load/thermal validation.

The complete host runner also exercises existing C++ policies and the offline
configurator. Their tests are separate from a flashable STM32 build or any
hardware test. The electrical CI preserves failing ERC/DRC release findings
as artifacts while checking structural consistency; its green structural job
must not be interpreted as manufacturing approval.

The final local host run passed five C++ suites, 78 Python/Qt tests plus 21
subtests, 23 static-interface tests, 12 resource tests and 24 GDI-contract tests.
The earlier failed run exposed stale tests expecting SENT3/4 to be unassigned;
those expectations were updated to the new explicitly provisional mappings.

## Remaining work and dependencies

| Blocker | Required next evidence/change |
| --- | --- |
| 24 low-side outputs | Implement PI8 + VVT4 + AUX PWM8 + service LS4, current/flyback ratings, controls and physical routing |
| GDI/HPFP | Resolve exact full PT2001 specifications, microcode/START allocation, DRVEN polarity, independent hardware inhibit, injector/pump data and protected power input; wire reviewed output banks to harness |
| Motor loads | Injector/pump/throttle/wastegate models are not selected. DRV8871 target ~1.75A is provisional and is not a continuous rating; driver may need replacement |
| Sensor interfaces | Protected sensor 5V rails and returns, four extra Hall inputs, DIN5..8, flex input, knock2 and WBO2 frontends |
| Communications/storage | CAN2, LIN2, USB and SD hardware and resource allocation |
| Resources/firmware | 9 required functions have no row; 28 rows remain unassigned; AF/DMA/timer/interrupt evidence and actual rusEFI F7 target absent |
| PCB | Functional placement of new domains, all missing routes, inherited GDI clearance/drill corrections, return paths and power/thermal budgets |
| Harness/mechanics | Four identical key1 headers can cross-mate; key selection, contact current and continuity checks pending. Older two-row CAD concept does not represent the actual four-row TE34 header |
| Fault qualification | Watchdog is not a per-channel dwell limiter; partial-power behavior, stuck channel with healthy heartbeat, overload/regeneration, EMC and physical fault injection remain untested |

The XML report lists 88 singleton HARNESS nets as incomplete electrical
interfaces. They were not silently attached to raw MCU GPIOs or unreviewed
power nodes. Sensor models being absent does not prevent continuing the digital
and interface work, but it prevents approving load-dependent final ratings.

Three workers supplied isolated core/IO, GDI/safety and PCB contributions.
All subsequently stopped at the account usage limit. Their original worktrees
were retained; integration recovered their uncommitted owned files and continued
locally. No additional live agents or seven simultaneous workers are claimed.

No ECU connection, flash, calibration write, actuation or manufacturing order
was performed. Component and source provenance remain in the domain documents;
the GDI4 source licensing uncertainty is explicitly retained.
