# Electrical review against exported XML — 2026-10-23

This pass read all seven actual XML netlists and compared device functions with
primary documents in `sources.json`. `reports/electrical_qa_snapshot.json` records
their hashes and the inspected IC/transistor/resistor pin maps. No new confirmed
motor schematic defect was identified in this pass. The review does identify
firmware sequencing requirements and unresolved physical fault cases; it is not
a repetition of the587 manifest/connectivity checks or a hardware qualification.

## SPI chain and voltage domains

| Physical path found in XML | Result |
|---|---|
| R6190.1 MOSI -> R6190.2 -> U6000.8 | First device is DBW |
| U6000.3 -> U6050.8 -> U6050.3 -> U6100.8 -> U6100.3 -> U6150.8 | DBW/EWG/Motor3/Motor4 order |
| U6150.3 -> U6190.2; U6190.4 -> R6192 -> MISO | Last SO is buffered |
| All TLE pin9 and U6190.1 = MOTOR_CS_N | Buffer is disabled when deselected |
| All TLE pin2 and U6190.5 = main3V3 | SO and buffer share a logic domain |
| All TLE pin10 = R6191 output MOTOR_SPI_SCK | One common clock |

[Infineon TLE9201SG Rev1.0, section4.12 and pp20–21](https://www.infineon.com/dgdl/Infineon-TLE9201SG-DS-v01_00-en.pdf?fileId=db3a304345087709014518190f481cec)
specifies falling-edge input sampling, rising-edge output update, and previous
command replies. Mode1/MSB-first,32 clocks and reversed wire byte order therefore
match this topology. There is no frame-length validator. SO error indication
exists after selecting and before the first clock, not while deselected.

At1MHz the500ns half-cycle accommodates230ns SO valid time plus40ns setup with
remaining interconnect/buffer margin; actual loading, clock skew and waveform
quality still need measurement. The static SO lower bound is VSO-0.75V at1mA:
2.55V at3.3V, above the following TLE/LVC input high requirement2V. This is not
an assertion of valid SPI when VSO or VS is outside its specified range.

## Shutdown paths and power topology

Each channel's pin11 connects to its OR-gate output; one input is global
HW_ACTUATOR_ENABLE_N, the other is the channel DISABLE. Both channel DISABLE
and final DIS have10k pull-ups. PWM/DIR have100ohm series and10k pull-downs.
All bridges use ground on pins6/13. DIS means all power FETs off; PWM=0 alone
does not disconnect a motor. Shutdown has up to80us device delay plus external
delays. VSO=0 selects sleep, but arbitrary partial-power transients are untested.

The XML supply paths are DBW/Motor3 -> MOTOR13_VS and EWG/Motor4 -> MOTOR24_VS.
For each LM74800, raw feed enters pins2/3, shared FET drains enter pins10/12,
the protected output enters pin9, charge-pump capacitor returns to the shared
drain node, and the exposed pad is unconnected. Both EN inputs receive positive
hardware enable through1k with10k to ground. Common-drain orientation blocks
raw-feed conduction when the output FET is disabled; output capacitors retain
energy and must not be treated as instantly discharged.

[TI LM7480-Q1 SNOSD95C](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf)
supports this controller topology. The existing calculated OV range is below
the TLE operating ceiling; TVS clamp voltage is a separate transient limit.
The source cannot sink motor regenerative energy through the ideal-diode path.
Actual load inertia, hot TVS pulse capacity, shared-feed connector/fuse limits,
and switching losses remain open. Two amps per bridge is a design envelope,
not a qualified or actively enforced continuous rating.

## Firmware startup requirement found during review

With global enable low, the LM74800 output switches remove TLE VS, so the
TLE internal logic may have no valid supply. Requiring valid motor SPI before
asserting global enable would create a startup deadlock. Establish all four
channel DIS inputs high first, enable the supply, wait for protected VS and
device startup, validate the pipelined four-device exchange, then enable only
the requested motor. The1ms wake-up maximum is not a replacement for measuring
the power-FET soft-start interval. The safe GPIO state must precede the global
arming edge and remain applied during the diagnostic phase.

Loss of either motor feed can break the mixed-feed SPI chain. A bad byte cannot
be assumed to belong only to one motor: reject the whole exchange and disable
all four until power and chain validity are restored. Serialize shared-bus access
with PT2001; change mode only with every chip-select high. Discard first/stale
pipeline data after resets. These are firmware integration requirements, not
implemented firmware behavior in this directory.

## Partial-power cases that remain unqualified

Root's new5V supervisor is necessary because main3V3 can persist while5V drops.
Motor supplies are independent of5V and could otherwise continue driving after
sensor or other driver domains become invalid. The supervisor must clear the
latch, assert DIS and remove motor supply without automatic re-arm.

The TLE DIS/CSN inputs have internal pull-up currents9..85uA. External pull-ups
to main3V3 and MCU/input clamps can be potential backfeed paths while protected
VS still contains energy. The datasheet does not explicitly identify every
pull-up's source during partial power; this is an **unresolved measurement case**,
not a confirmed short or a guaranteed current source. Inspect dead-main3V3 rail
voltage and VSO, including an unpowered MCU or debugger and each feed separately.
The SO high-side body diode also forbids driving SO above VSO+0.3V; the normal
chain has a shared VSO rail and no external SO pull-up, but fault injection must
include mismatched supplies and probes.

Required records: shutdown under stall/current, both supply-loss orders, retained
VS/main3V3 loss, one-feed removal, stuck clock/CS/data, regenerative braking,
thermal soak, and hot/cold startup. Capture all DIS/VSO/VS and output currents.
No electrical, firmware timing, thermal or fault-injection bench case was marked
PASS by this review. Root integration/PCB DRC remains the coordinator's work.
