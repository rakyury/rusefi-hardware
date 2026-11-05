"""Eight passive-coil ignition stages; engineering candidate, not engine qualified.

The optional logic assembly is a separate generated design, never a software mode
or a DNP bypass across the passive assembly's high-voltage collector net.
"""
from pathlib import Path
import argparse
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from core_schlib import Sheet, box_symbol, uid

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"


def device(name, names, kinds, footprint, prefix="U"):
    # Explicit datasheet pin numbers, alternated around a drawing box.
    n = len(names)
    left = (n + 1) // 2
    pins = []
    for i, (pin, label) in enumerate(names):
        side = i < left
        row = i if side else i-left
        y = ((left-1)/2-row)*5.08
        pins.append((str(pin), label, kinds.get(label, "input"),
                     -20.32 if side else 20.32, y, 0 if side else 180))
    return box_symbol(name, pins, footprint, width=35.56,
                      height=(left-1)*5.08+2.54, prefix=prefix)


def symbols():
    return {
        "timer": device("LTC6993HS6_1", [(1,"TRIG"),(2,"GND"),(3,"SET"),(4,"DIV"),(5,"V+"),(6,"OUT")],
            {"GND":"power_in","V+":"power_in","SET":"passive","OUT":"output"}, "Package_TO_SOT_SMD:TSOT-23-6"),
        "and": device("SN74LVC1G11B_Q1", [(1,"A"),(2,"GND"),(3,"B"),(4,"Y"),(5,"VCC"),(6,"C")],
            {"GND":"power_in","VCC":"power_in","Y":"output"}, "Package_TO_SOT_SMD:SOT-363_SC-70-6"),
        "buffer": device("IGN_SN74LVC1G17_Q1", [(1,"NC"),(2,"A"),(3,"GND"),(4,"Y"),(5,"VCC")],
            {"NC":"no_connect","GND":"power_in","VCC":"power_in","Y":"output"}, "Package_TO_SOT_SMD:SOT-23-5"),
        "driver": device("UCC27524AQDRQ1", [(1,"ENA"),(2,"INA"),(3,"GND"),(4,"INB"),(5,"OUTB"),(6,"VDD"),(7,"OUTA"),(8,"ENB")],
            {"GND":"power_in","VDD":"power_in","OUTA":"output","OUTB":"output"}, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"),
        "igbt": box_symbol("STGB18N40LZT4", [("1","G","input",-20.32,7.62,0),("2","C_TAB","passive",-20.32,-7.62,0),("3","E","passive",20.32,-7.62,180)],
            "Package_TO_SOT_SMD:TO-263-2",width=35.56,height=17.78,prefix="Q"),
        "monitor": device("INA300AQDGSRQ1", [(1,"IN+"),(2,"IN-"),(3,"LIMIT"),(4,"ENABLE"),(5,"ALERT_N"),(6,"LATCH"),(7,"DELAY"),(8,"GND"),(9,"VS"),(10,"HYS")],
            {"ALERT_N":"open_collector","GND":"power_in","VS":"power_in","LIMIT":"passive"}, "Package_SO:VSSOP-10_3x3mm_P0.5mm"),
    }


def calculations():
    rlimit, shunt = 4990, 0.010
    # INA300: ILIMIT extrema, component tolerances and conservative drift budget.
    rohm = .01 + 25e-6*100
    rshunt = .01 + 75e-6*100
    offset = (650+50+45+120)*1e-6
    low = (19.85e-6*rlimit*(1-rohm)-.0005-offset)/(shunt*(1+rshunt))
    high = (20.15e-6*rlimit*(1+rohm)-.0005+offset)/(shunt*(1-rshunt))
    pulse = 4096*147000/50000*1e-6
    return {"trip_nominal_A":(20e-6*rlimit-.0005)/shunt,
            "trip_threshold_budget_A":[low,high], "dynamic_peak_current_bounded":False,
            "window_nominal_ms":pulse*1000,
            "window_component_budget_ms":[pulse*(1-rohm)*.977*1000,pulse*(1+rohm)*1.023*1000],
            "energy_at_3mH_and_upper_threshold_mJ":.5*.003*high**2*1000,
            "status":"Unqualified; delay overshoot and hot repetitive energy require bench measurement"}


def make_ignition(syms, root_id, variant="passive"):
    if variant not in ("passive", "logic"):
        raise ValueError("assembly must be passive or logic")
    d = symbols()
    stem = "ignition" if variant == "passive" else "ignition/logic_variant"
    def res(s, ref, val, x, y, a, b, note="", footprint=FP_R):
        s.component(syms["R"],ref,val,x,y,{"1":a,"2":b},footprint=footprint,note=note)
    def cap(s, ref, x, y, rail, value="100n 25V X7R"):
        s.component(syms["C"],ref,value,x,y,{"1":rail,"2":"GND"},footprint=FP_C)
    common = Sheet(stem+"/ignition_common", "Ignition permission and three dual gate drivers", root=root_id, paper="A2")
    sheets = [common]
    common.text("PASSIVE PRIMARY OUTPUT ASSEMBLY" if variant == "passive" else "SEPARATE LOGIC OUTPUT ASSEMBLY - NOT B58 PASSIVE COILS",25,20,2)
    common.text("IGN_OC_OK is open drain, healthy high. Parent connects to HW_KILL_N.\nNo firmware-only current limit. Fault turn-off can cause an unintended spark.\nCoil +12V feed must be removed on fault; see HW_IGNITION_B58.md.",25,35)
    common.component(d["buffer"],"U5400","SN74LVC1G17QDBVRQ1",100,90,{"2":"IGN_OC_OK","3":"GND","4":"IGN_OC_OK_CLEAN","5":"+3V3"})
    common.component(d["and"],"U5401","SN74LVC1G11BDCKRQ1",270,90,{"1":"HW_ACTUATOR_ENABLE","2":"GND","3":"IGN_OC_OK_CLEAN","4":"IGN_SAFE_EN","5":"+3V3","6":"+3V3"})
    res(common,"R5400","10k 1%",420,70,"+3V3","IGN_OC_OK")
    res(common,"R5401","1k",480,70,"IGN_SAFE_EN","GND","3.3mA load; holds driver EN below threshold against internal 200k typical pullups when logic is unpowered.")
    cap(common,"C5400",420,130,"+3V3")
    cap(common,"C5401",480,130,"+3V3")
    for pair in range(3):
        a,b=pair*2+1,pair*2+2
        x,y=110+(pair%2)*270,210+(pair//2)*100
        common.component(d["driver"],f"U{5402+pair}","UCC27524AQDRQ1",x,y,{"1":"IGN_SAFE_EN","2":f"IGN{a}_GUARDED","3":"GND","4":f"IGN{b}_GUARDED","5":f"IGN{b}_DRIVE","6":"+5V_CORE","7":f"IGN{a}_DRIVE","8":"IGN_SAFE_EN"},note="Automotive grade 1; SOIC-8 D package (not PowerPAD DGN). UVLO holds outputs low. 5A is peak gate drive, not coil current.")
        cap(common,f"C{5402+pair*2}",x+85,y-20,"+5V_CORE")
        cap(common,f"C{5403+pair*2}",x+85,y+20,"+5V_CORE","1u 25V X7R")
    for ch in range(1,7):
        n=5420+(ch-1)*20
        p=f"IGN{ch}"
        s=Sheet(f"{stem}/ignition_{ch}",f"Ignition {ch} - {'timed primary and OC latch' if variant=='passive' else 'timed logic output'}",root=root_id,paper="A2")
        sheets.append(s)
        s.text(f"Channel {ch} / {variant} assembly / unqualified candidate",25,20,2)
        s.text("LTC6993-1: rising edge, NON-retriggerable. 12.042 ms nominal window.\nGate = command AND window AND hardware permission. Not a dwell calibration.",25,35)
        s.component(d["timer"],f"U{n}","LTC6993HS6-1#WTRPBF",110,95,{"1":p,"2":"GND","3":p+"_SET","4":p+"_DIV","5":"+3V3","6":p+"_WINDOW"})
        s.component(d["and"],f"U{n+1}","SN74LVC1G11BDCKRQ1",300,95,{"1":p,"2":"GND","3":p+"_WINDOW","4":p+"_GUARDED","5":"+3V3","6":"IGN_SAFE_EN"})
        res(s,f"R{n}","100k",50,165,p,"GND")
        res(s,f"R{n+1}","147k 1% 25ppm",160,165,p+"_SET","GND")
        res(s,f"R{n+2}","100k 1%",270,165,"+3V3",p+"_DIV")
        res(s,f"R{n+3}","39.2k 1%",380,165,p+"_DIV","GND")
        res(s,f"R{n+4}","100k",490,165,p+"_GUARDED","GND")
        cap(s,f"C{n}",160,210,"+3V3")
        cap(s,f"C{n+1}",300,210,"+3V3")
        if variant == "logic":
            res(s,f"R{n+5}","100R",470,95,p+"_DRIVE",f"HARNESS_IGN{ch}")
            res(s,f"R{n+6}","10k",470,210,f"HARNESS_IGN{ch}","GND")
            s.text("Separate BOM/netlist/PCB assembly. No primary current monitor in logic variant.\nDo not fit passive coils; no high-voltage IGBT is present.",25,260)
            continue
        s.component(d["igbt"],f"Q{n}","STGB18N40LZT4",480,95,{"1":p+"_GATE","2":f"HARNESS_IGN{ch}","3":p+"_SHUNT_HI"},note="Collector/tab 360..420V clamp. No low-voltage TVS or flyback diode across coil.")
        res(s,f"R{n+5}","10R",50,255,p+"_DRIVE",p+"_GATE")
        res(s,f"R{n+6}","10k",160,255,p+"_GATE",p+"_SHUNT_HI")
        res(s,f"R{n+7}","WSLP2512R0100FEA",300,255,p+"_SHUNT_HI","GND","10mOhm 1% 3W; Kelvin sense; dedicated power return copper.","Resistor_SMD:R_2512_6332Metric")
        s.component(d["monitor"],f"U{n+2}","INA300AQDGSRQ1",140,330,{"1":p+"_SHUNT_HI","2":"GND","3":p+"_ILIMIT","4":"+3V3","5":"IGN_OC_OK","6":"+3V3","8":"GND","9":"+3V3"},note="DELAY and HYS intentionally float: 10us typical, 2mV. LATCH high; power cycle required to clear.")
        res(s,f"R{n+8}","4.99k 1% 25ppm",330,325,p+"_ILIMIT","GND","E96 value; initial nominal 9.93A trip; not a qualified B58 full-power limit.")
        cap(s,f"C{n+2}",470,325,"+3V3")
        s.text("IN+/IN- route as a Kelvin pair to shunt pads; do not carry ignition current in logic ground.\n10us is typical comparator response, NOT a guaranteed maximum short-circuit delay.\nOvercurrent latches all eight channels off through IGN_OC_OK until power cycle.\nHard cut-off may spark; soft shutdown and repetitive avalanche survival are NOT claimed.",25,375,1.15)
    return sheets


def generate(variant="passive"):
    from build_core_schematic import load_symbols
    sheets = make_ignition(load_symbols(), uid("Power8GDI_Core"), variant)
    for s in sheets:
        s.write(HERE.parent)
    dest = HERE if variant == "passive" else HERE/"logic_variant"
    (dest/"ignition_manifest.json").write_text(json.dumps({"variant":variant,"calculations":calculations(),"parts":[p for s in sheets for p in s.parts]},indent=2)+"\n",encoding="utf-8")
    print(f"Generated {len(sheets)} sheets, {sum(len(s.parts) for s in sheets)} components ({variant})")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",choices=["passive","logic"],default="passive")
    generate(parser.parse_args().variant)
