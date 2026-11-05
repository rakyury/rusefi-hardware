# Independent electrical review — 2026-10-23

The inspected artifacts are the actual six KiCad XML netlists, not just the
generated component manifest. This review found and corrected a real inherited
power-sequencing defect. Electrical topology is verified; hardware behavior is
not measured or qualified.

## Confirmed defect and correction

[ST STM32F042 DocID025832 Rev5, section3.5](https://www.st.com/resource/en/datasheet/stm32f042k6.pdf)
requires VDDA to remain at least VDD and to be established first. Old XML had
U5602.1/.17 on XC6206 and U5602.5 on REF3033, both nominal3.3V. Equal nominal
ratings do not guarantee ordering or tolerance. The F042 POR only monitors VDD;
its low reset threshold is also insufficient to establish valid ADC operation.

U5604/U5804 are now **LT3042IMSE#WTRPBF** reference buffers. Their common output
powers MCU VDD and VDDA, the analog amplifiers and local CAN VIO. U5603/U5803
REF3033 remain precision setpoints and do not carry the digital load. Separate
local nets remain isolated from the main3V3. Nominal firmware3.3V scaling is
retained, with the small calculated offset below included in calibration review.

[ADI LT3042 RevC](https://www.analog.com/media/en/technical-documentation/data-sheets/lt3042.pdf)
permits an external SET reference (p15). Its SET source is98..102uA; PGFB tied to
IN disables fast start. SET clamp current is limited to20mA (p22). We add220ohm
series resistance and30kohm to ground, both0.1%, giving nominal3.297816V from
3.3V. The bleed exceeds102uA, so REF normally sources a small positive current.
Even a SET short draws under15.2mA through220ohm at3.33V. The 2mV buffer offset
bound adds to reference error, not to a second independent supply mismatch.

OUTS is the same net as OUT and must Kelvin-connect at its capacitor. CIN/COUT
each reserve10uF16V1206, **effective capacitance at least4.7uF** across bias and
temperature; ESR/ESL and exact assembly MPN remain layout/BOM gates. Output2.2k
bleed maintains over1mA for specified offset conditions. Added local100n bypasses
serve SET, REF and reset supervisor. MSOP10 pin11 is grounded; footprint body3x3,
pitch0.5, EP1.68x1.88 match datasheetp30. It replaces the old SOT23 placement.

U5612/U5812 [TPS3808G33QDBVRQ1, SBVS085J](https://www.ti.com/lit/ds/symlink/tps3808-q1.pdf)
monitor local3V3 and pull F042 NRST low at nominal3.07V. CT is open, giving
nominal20ms release delay; NRST has10k local pull-up and the retained1uF capacitor.
SENSE/MR/VDD all use the local rail; no5V signal enters these pins. This provides
a defined reset while the rail settles and before slow droop reaches ADC minimum.
The inherited large NRST capacitor adds assertion/release dynamics requiring
measurement; it is not counted as zero-delay shutdown.

## Independent evidence and scope

`verify_wbo.py::supply_errors` asserts the replacement devices' manufacturer pin
contracts directly against exported XML. It does not use `parts.json`, mapper or
`reference_map.json` to define expected supply/reset connections. Eight mutations
(split VDDA, REF directly loaded, fast-start enabled, wrong reset-sense domain)
are rejected. The original connected-pin partition audit still rejects all six
op-amp +/- collision mutations. Its only supply adaptation is the explicit
VDDA/+3V3 merge, U604 replacement and U603 output relocation. No signal-net
exception or ERC exclusion was introduced. Current export after the separate OE correction:174parts,420 checks.

Standalone ERC is7 analog/10 control/1 heater-feed findings per channel, consisting
of cross-sheet/external-driver findings. Integrated root ERC remains required.
The source analog-loop topology is preserved; sharing a precision supply changes
the noise coupling and must be validated with ADC/lambda calibration on hardware.

## Power-loss, reset and backfeed review

The local LVC AND gate receives F042 PWM and main permission. Reset makes F042 PWM
high impedance; the fitted1k PWM pull-down and downstream pull-downs remove its
request. AHCT output is independently inhibited by loss of positive HW_ACTUATOR_ENABLE
through the local default-disabled level shifter described below.
Main permission remains required after CAN recovery. A frozen F042 PWM is **not**
independently detected here; main firmware must reject stale/invalid CAN and clear
permission. No extra heartbeat guarantee is claimed.

[TI SN74AHCT1G125-Q1 RevE](https://www.ti.com/lit/ds/symlink/sn74ahct1g125-q1.pdf)
specifies operation from3V, but heater switch on-resistance is specified at5V
input. Therefore continued partial5V operation is unacceptable even if logic
still switches. Root's added independent5V monitor must latch global shutdown
while main3V3 is still valid; monitoring main3V3 alone misses that condition.
LP5_PG_RAW is a5V-domain node and must not directly join3V3 fault inputs.

The LVC permission input has partial-power support. CAN VIO and F042 have the
same local rail. Neither SWD nor external test equipment may power an unpowered
module through signal pins. The LT buffer blocks reverse output-to-input flow,
but the SET/REF branch and external interfaces remain possible discharge paths;
do not infer total backfeed isolation from that regulator feature.

Required measurements: slow and abrupt5V loss with main3V3 retained, local-rail
short, independent main/local reset, debug-powered case, F042 hung with PWM high,
CAN loss/recovery, and ignition/motor transients. Capture local VDD/VDDA, NRST,
SET/REF,5V, global inhibit and heater input/current together. Verify no heater
restart without fresh main permission. Check reference settling, digital-noise
coupling, local LDO load/temperature and hot/low-battery heater drive. None of
these bench conditions is marked PASS by the XML checks.

Primary documents were inspected through manufacturer-hosted PDF tools. Local
LT3042 PDF download timed out; no captured PDF/hash is claimed. URLs/revisions
above are the evidence; the older rejected STPS mirror remains explicitly unused.

## Separate correction: main3V3 absent while local5V remains

The earlier U5611/U5811 OE connection to HW_ACTUATOR_ENABLE_N depended on a
main3V3 pull-up. With main3V3 off, OE could be low while the5V buffer remained
powered. Individual permission default-off did not establish an independent
hardware inhibit. This was reported by the independent GDI review after the
common-supply correction and is fixed in a separate commit.

R5642/R5842 now pull local HEATER_OE_N to **+5V_CORE through2.2k**. BC847B-QR
Q5620/Q5820 pulls OE low only when positive HW_ACTUATOR_ENABLE is present.
Base drive is4.7k; base-to-ground is10k. The5V collector never directly joins
U804 or any main3V3 signal. Main permission and the global inhibit remain
independent inputs to the final heater request.

[Nexperia BC847x-Q Rev2, pp2/4](https://assets.nexperia.com/documents/data-sheet/BC847X-Q_SER.pdf)
confirms1B/2E/3C and the SOT23 package. At nominal3.3V/0.7V base voltage, each
channel draws about0.55mA from global enable and has about0.48mA transistor
base current; collector current is about2.2mA. Integration must budget the
combined~1.1mA added load on U804. This is a switching design calculation,
not a measured transistor transfer curve over temperature.

AHCT OE uses VIH2V/VIL0.8V at4.5..5.5V. For the static main3V3=0/local5V=4.5V
fault case,6uA total leakage allowance across2.2k+1% leaves OE above4.486V.
The base10k limits5uA collector-base leakage to roughly50mV even if the main
output is high impedance. The exact transistor/logic partial-power behavior
still needs hot/cold measurement. With an erroneously restored3V3 pull-up,
the same actual-netlist DC scenario computes OE near0V and fails.

Eight new net mutations cover wrong pull-up domain, direct negative-enable
connection, inverted enable polarity and missing base discharge. Four static
scenario checks additionally compare the correct circuit with the previous
3V3-domain pull-up. These are topology/DC checks, not SPICE transient evidence.
AHCT input transition limits also apply:2.2k reduces the OE rise time, and the
collector/OE connection must remain short with no added shunt capacitor.
Measure OE edges and storage delay at temperature; abrupt5V collapse below
its valid range is still covered by the root5V latch/bench fault plan.
