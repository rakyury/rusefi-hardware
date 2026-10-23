# WBO engineering checkpoint - 2026-10-23

CURRENT ENGINEERING CHECKPOINT: local work resumed after cancelled handoff.
All six netlists exported again with KiCad9.0.9 after final signal/layout changes.
396 connectivity, independent topology, power/reset and footprint-pad checks pass. Standalone leaf ERC findings are
cross-sheet global labels and missing external power drivers only (7/10/1 per
channel); final integrated ERC remains the integration lead's responsibility.
No manufacturing, thermal, EMC or engine qualification is claimed.

## Implemented

Six generated KiCad sheets, 168 actual components: two independent on-board
F042 WBO channels derived electrically from Hellen WBO0.6. Removes dependency
on unresolved CJ125 pin18 and adds actual heater switches and protected feeds.
Parent integration must replace interfaces_aux/wbo1_analog, wbo2_analog and
wbo_adc_control, retaining knock_dual. New references use5600/5800 banks.
Existing HARNESS_WBO1/2_CONTACT1..6 map Bosch automotive LSU4.9 pins:
1 Ip;2 Vm;3 heaternegative;4 heaterpositive;5 Rtrim;6 Un.
No external WBO controller required. No EGT electronics in this ECU.

Hellen source net LSU_H+ is misleading in0.6: it is Q600 low-side drain and
moduleE5 LSU_Htr. Our net maps it to actual sensor heaternegative contact3.
TJA1051 pin6 CANL and7 CANH are verified; do not copy known0.4 reversed CAN.

## Integration contract

CAN2_H/L shared existing bus,500kbit/s. Data IDs400/402 and diagnostic401/403.
Index0 uses SEL1low/SEL2floating; index1 uses SEL1floating/SEL2high as pinned
f0_module port.cpp. Per-node120R termination DNP.
+5V_CORE feeds local3.3V LDO/reference and transceiver; local3.3V never joins
main3.3V. Main3.3V used only inhibit pull-up. Heater feed VBAT_MAIN_FUSED,
NOT VBAT_LOGIC_PROTECTED (existing logic diode cannot carry heaters).
Main MCU legacy WBO1_HEATER_PWM/WBO2_HEATER_PWM are static permissions;
actual local PWM is WBO1/2_F042_HEATER_PWM. LVC1G08 AND + AHCT1G1255Vbuffer
implements localPWM AND mainpermission AND NOT(HW_ACTUATOR_ENABLE_N).
Mainfirmware must clear permission on stale/invalid CAN. This is not an
independent F042 hardware heartbeat. Calibration/thermal/fault tests pending.

Heater switches use active VND7NV04TR-E DPAK replacing obsolete VNN7NV04
SOT223. Reverse diode STPS5H100BY-TR DPAK verified against ST DS6906p1
render: pin1 NC, pin2/tab cathode, pin3 anode. Pins1/3 must NOT be swapped.
Heater supply diode drop requires compensation in voltage sent over CAN;
no local heater voltage ADC is currently added. Branchfuses/currentreturn/
cold-start and transient coordination remains integration work.

## Validation

Run build_wbo.py, export every wbo*.kicad_sch with kicad-cli sch export netlist
--format kicadxml, then run verify_wbo.py inside the pinned KiCad9 image.
Latest396 checks pass against the regenerated electrical sheets and all installed
footprint pads. Pin contracts cover Bosch sensor mapping, ST diode/FET mapping,
CAN polarity, F042 pins, power isolation and all heater inhibit gates.
Control and analog previews were inspected; sheet overflow and reference-label
overlap corrected. Saved SVG/PNG previews are illustrative snapshots, not release
artifacts. Root integration and routed-board DRC remain outside this module scope.

## Provenance / rights

Hardware: https://github.com/rusefi/hellen-one
Pinned f8be5db671b7a2739d0c5c2ee7c9a80c3022aa76,
kicad/modules/hellen1-wbo/hellen1-wbo.kicad_sch, revision0.6 dated2026-03-22.
Rawsource/PCB and KiCadexportXML captured underreference; originals unmodified.
GitHub repo metadata license:null; noLICENSE found. Hardware redistribution
permission remains unresolved. reference/LICENSE belongs ONLY to separately
captured rusefi/wideband firmware (MIT), not to Hellen hardware.
Firmware commit in reference/firmware_commit.txt, files from
https://github.com/rusefi/wideband/firmware/boards/f0_module andwideband-can.dbc.

Primarycomponent sources:
https://www.st.com/resource/en/datasheet/vnd7nv04.pdf
https://www.st.com/resource/en/datasheet/stps5h100-y.pdf
https://www.ti.com/product/SN74LVC1G08-Q1
https://www.ti.com/product/SN74AHCT1G125-Q1
https://www.bosch-motorsport.com/content/downloads/Raceparts/en-GB/51865867208058251.html

reference/stps5h100-y-mirror.pdf is an HTML rejection downloaded from Mouser,
not avalidPDF. Preserved forhandoff pernodeletion instruction; do not use.
OfficialSTPDF download timedout; webPDF rendered via search_service screenshot
successfully and pinout read visually. No physicalhardwarequalification claim.

## Critical analog-net correction after integration review

The original generic punctuation sanitizer incorrectly merged three pairs of
distinct op-amp input nets in each channel: U600A +/-, U600B +/-, U601 +/-.
Earlier332 manifest-based checks did not detect this and are insufficient evidence
of analog topology. Do not use the electrical exports through commit de91746.

Automatic source nets now use reversible UTF-8 byte escaping, including underscores,
and a reserved AUTO_ prefix. A generator guard rejects alias collisions except the deliberately documented
VDDA/+3V3 common-supply merge in ELECTRICAL_QA.md. The added independent audit reads the original Hellen XML and compares
entire connected-pin partitions with the real target XML, without reference_map or
the generator's alias function. Only documented adaptation pins are removed from
comparison: omitted module-frame/R630/C604/C606, Q600 extra SOT223 drain pad4,
R622.2 moved behind the safety buffer, and the selected floating ternary-ID pin.
The later supply fix additionally replaces U604, moves U603.2 to the reference
setpoint and merges only the source VDDA/+3V3 partitions. Every retained signal
connection must remain in exactly the same partition; a separate manufacturer
pin contract checks the replacement supply and reset circuitry.

The prior collision-fix checkpoint had346 passing checks, including independent source topology for both channels and
six deliberate +/- collision mutations rejected. The same independent audit also
rejects the actual old de91746 netlists, with six changed source-net partitions per
channel (`reports/legacy_collision_rejection.json`). Regenerated schematics, XML,
ERC and SVG/PNG previews supersede the earlier exports. Physical calibration and
integrated-board validation are still required.

## Read-only interface findings given to integrationlead

LIN1 originally lackedmasterpullup; LIN2 optional1k+diode DNP responderonly.
Parent nowaddingboth masterpullups percontract. SENT4frontend is5Vonly10k/47k,
47pF, clampsandLVCinverter. Firmware must invertedgepolarity andsupportsensor
fast/slowchannels, CRC, timestamps/timeouts. No universalSENTsensorprofiling.
ExternalEGT CAN500k matchesWBO. Exactprotocol/IDs andbusutilizationnotfrozen;
reserve noanalogthermocoupleconnections inECUharness.

## Power sequencing correction

See [ELECTRICAL_QA.md](ELECTRICAL_QA.md) for the confirmed F042 supply defect,
reference-buffer correction, independent mutation checks and remaining measured
fault/ADC/thermal requirements. The local3V3 rail now supplies both VDD and VDDA;
REF3033 supplies only the LT3042 setpoint. Do not restore the independent XC6206.
