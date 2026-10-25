"""Generate the connected, explicitly unqualified Power8GDI core candidate."""
from __future__ import annotations
import csv
import json
from pathlib import Path

from core_schlib import Sheet, Symbol, box_symbol, child, children, dump, parse, q, uid
from build_core_io import ANALOG, make_io
from outputs.build_outputs import make_outputs
from ignition.build_ignition import make_ignition

HERE=Path(__file__).resolve().parent
HARDWARE=HERE.parent
ROOT_ID=uid("Power8GDI_Core")
FP_C="Capacitor_SMD:C_0603_1608Metric"
FP_R="Resistor_SMD:R_0603_1608Metric"
FP_SO8="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"


def load_symbols():
    data=parse((HERE/"core_sources/core_selected.kicad_sym").read_text(encoding="utf-8"))
    result={}
    for expr in children(data,"symbol"):
        name=str(expr[1]).split(":")[-1]
        props={str(p[1]):str(p[2]) for p in children(expr,"property")}
        result[name]=Symbol(name,dump(expr),props.get("Footprint",""))
    return result


def generate():
    syms=load_symbols()
    mcu_symbol=syms["STM32F767IIT6"]
    assert len(mcu_symbol.pins)==176 and set(mcu_symbol.pins)=={str(i) for i in range(1,177)}
    r,c=syms["R"],syms["C"]
    root=Sheet("Power8GDI_Core","Power8GDI core and interfaces",paper="A0")
    mcu=Sheet("core_mcu","MCU, power decoupling and debug",root=ROOT_ID,paper="A2")
    comm=Sheet("core_comms","CAN1 and LIN1 physical interfaces",root=ROOT_ID,paper="A2")
    ignition_sheets=make_ignition(syms,ROOT_ID)
    sheets=[root,mcu,comm]+ignition_sheets
    def cap(sheet,ref,value,x,y,net,note="",footprint=FP_C):
        sheet.component(c,ref,value,x,y,{"1":net,"2":"GND"},footprint=footprint,note=note)
    def res(sheet,ref,value,x,y,a,b,note="",dnp=False):
        sheet.component(r,ref,value,x,y,{"1":a,"2":b},footprint=FP_R,note=note,dnp=dnp)

    pin_by_name={p["name"]:n for n,p in mcu_symbol.pins.items()}
    gpio=list(csv.DictReader((HARDWARE/"mcu_gpio_draft.csv").open(encoding="utf-8-sig")))
    nets={}
    for n,p in mcu_symbol.pins.items():
        name=p["name"]
        if name in {"VDD","VDDUSB","VDDSDMMC","VBAT","PDR_ON"}: nets[n]="+3V3"
        elif name in {"VSS","VSSA","VREF-","BYPASS_REG"}: nets[n]="GND"
        elif name in {"VDDA","VREF+"}: nets[n]="+3V3_A"
        elif name.startswith("VCAP"): nets[n]="MCU_"+name
    for row in gpio:
        if row["stm32_pin"]!="UNASSIGNED":
            n=pin_by_name[row["stm32_pin"]]
            if n in nets: raise ValueError("GPIO collides with core: "+row["function"])
            nets[n]=("ADC_" if row["function"] in {x[0] for x in ANALOG} else "")+row["function"]
    for name,net in {"NRST":"NRST","BOOT0":"BOOT0","PA13":"SWDIO","PA14":"SWCLK","PB3":"SWO","PH0":"MCU_HSE_IN","PH2":"CAN1_STB","PH3":"LIN1_EN"}.items():
        n=pin_by_name[name]
        if n in nets and nets[n]!=net: raise ValueError("Core pin already assigned: "+name)
        nets[n]=net
    mcu.hport("+3V3",25.4,25.4)
    mcu.hport("GND",25.4,33.02)
    mcu.component(mcu_symbol,"U101","STM32F767IIT6",152.4,177.8,nets,
                  note="Provisional industrial -40..85C LQFP176. Unassigned pads are intentionally unused in this candidate, not qualified resources.")
    mcu.text("176 physical pads; source: DS11532 Rev9 + official KiCad9.0.9 symbol.\nGPIO labels are logic-side draft functions, NEVER harness/actuator connections.\nUSB FS and SPI3 microSD use dedicated interface sheets. PH1, PC14/15 reserved unused; HSE bypass input only.",250,25.4)
    vdd=[n for n,p in mcu_symbol.pins.items() if p["name"]=="VDD"]
    decoupling=[]
    for i,n in enumerate(sorted(vdd,key=int)):
        ref="C"+str(101+i)
        cap(mcu,ref,"100n 16V X7R",260+(i%6)*43.18,65+(i//6)*43.18,"+3V3",f"Place directly at U101 VDD pad {n}; short GND return")
        decoupling.append({"reference":ref,"mcu_pad":n,"rail":"+3V3"})
        mcu.text("U101 pad "+n,250+(i%6)*43.18,80+(i//6)*43.18,1.016)
    cap(mcu,"C114","4.7u 16V X7R",260,195,"+3V3","Package bulk; effective capacitance >=4.7uF after bias/temp derating")
    cap(mcu,"C115","2.2u 10V X7R",303.18,195,"MCU_VCAP_1","U101 pad81; effective2.2uF ESR<2ohm; no external load")
    cap(mcu,"C116","2.2u 10V X7R",346.36,195,"MCU_VCAP_2","U101 pad125; effective2.2uF ESR<2ohm; no external load")
    cap(mcu,"C117","100n 16V X7R",389.54,195,"+3V3_A","U101 VDDA39/VREF38")
    cap(mcu,"C118","1u 16V X7R",432.72,195,"+3V3_A","U101 VDDA39/VREF38")
    res(mcu,"R101","0R",475.9,195,"+3V3","+3V3_A","Analog star feed; ferrite substitution needs transient/ADC review")
    for i,(pad,rail) in enumerate([("114","VDDUSB"),("149","VDDSDMMC")]):
        cap(mcu,"C"+str(119+2*i),"100n 16V X7R",260+i*86.36,245,"+3V3",f"U101 {rail} pad{pad}")
        cap(mcu,"C"+str(120+2*i),"1u 16V X7R",303.18+i*86.36,245,"+3V3",f"U101 {rail} pad{pad}")
    cap(mcu,"C123","100n 16V X7R",432.72,245,"+3V3","VBAT U101 pad6; no backup battery")
    cap(mcu,"C124","100n 16V X7R",260,300,"NRST","DS11532 Fig41 reset filter; connect debugger open-drain reset")
    res(mcu,"R102","10k",303.18,300,"+3V3","NRST")
    res(mcu,"R103","10k",346.36,300,"BOOT0","GND","Default flash boot; option bytes still require firmware review")
    swd=box_symbol("Debug_2x05",[(str(i),name,"passive",-10.16 if i%2 else 10.16,10.16-((i-1)//2)*5.08,0 if i%2 else 180)
                              for i,name in enumerate(["VTREF","SWDIO","GND","SWCLK","GND","SWO","KEY","NC","GND","NRST"],1)],
                   "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical",width=15.24,height=25.4,prefix="J")
    mcu.component(swd,"J101","SWD 3V3 target reference",440,310,
                  {"1":"+3V3","2":"SWDIO","3":"GND","4":"SWCLK","5":"GND","6":"SWO","9":"GND","10":"NRST"},
                  note="VTREF sense only, not external power input. Pin7 key/unused, pin8 unused; unshrouded header")
    mcu.text("Safety, crank and analog frontends are connected; remaining output domains and timing need review.\nIGN1=PC13 remains draft: low-drive restrictions require high-impedance buffer.\nNo MCU output is connected directly to a coil, injector, solenoid or vehicle wire.",250,355)
    oscillator=box_symbol("ASEM1_8MHz",[("1","EN","input",-10.16,5.08,0),("3","OUT","output",10.16,0,180),
                         ("4","VDD","power_in",0,10.16,270),("2","GND","power_in",0,-10.16,90)],
                         "Power8GDI_Core:ASEM_3225",width=15.24,height=15.24,prefix="Y")
    mcu.component(oscillator,"Y101","ASEM1-8.000MHZ-LC-T",75,330,
                  {"1":"+3V3","2":"GND","3":"MCU_HSE_IN","4":"+3V3"},
                  note="Abracon ASEM RevP p4 actual pins1EN2GND3OUT4VDD; firmware HSE bypass required; PH1 NC")
    cap(mcu,"C129","10n 16V X7R",120,330,"+3V3","Abracon recommends10n between Y101 pins4/2; short return")
    mcu.text("8MHz CMOS HSE: bypass mode required.\nOscillator load <=15pF, start<=3ms.\nClock tree/USB48MHz firmware review pending.",25.4,365)

    can=box_symbol("TCAN1042HGV_Q1",[("1","TXD","input",-12.7,7.62,0),("4","RXD","output",-12.7,0,0),("8","STB","input",-12.7,-7.62,0),
                   ("7","CANH","bidirectional",12.7,5.08,180),("6","CANL","bidirectional",12.7,-5.08,180),
                   ("3","VCC","power_in",-2.54,15.24,270),("5","VIO","power_in",2.54,15.24,270),("2","GND","power_in",0,-15.24,90)],FP_SO8,width=20.32,height=25.4)
    comm.hport("+3V3",25.4,25.4)
    comm.hport("+5V_CORE",25.4,33.02)
    comm.hport("GND",25.4,40.64)
    comm.component(can,"U103","TCAN1042HGVDRQ1",125,90,{"1":"CAN1_TX","4":"CAN1_RX","8":"CAN1_STB","7":"CAN1_H","6":"CAN1_L","3":"+5V_CORE","5":"+3V3","2":"GND"},note="STB held high at reset; MCU PH2 pad43 may drive low to enable; GPIO firmware pending")
    cap(comm,"C127","100n 16V X7R",205,65,"+5V_CORE","At U103 pin3")
    cap(comm,"C128","100n 16V X7R",245,65,"+3V3","At U103 pin5")
    res(comm,"R104","10k",65,90,"+3V3","CAN1_STB","Fail-closed default: transceiver in standby")
    res(comm,"R105","0R DNP",65,140,"CAN1_STB","GND","Test-only normal-mode strap; leave DNP for MCU PH2 control",dnp=True)
    res(comm,"R106","120R DNP",205,120,"CAN1_H","CAN1_L","Fit only if ECU is a bus end; do not add third terminator",dnp=True)
    comm.text("CAN1_H/L are vehicle-side nets. STB high by default; MCU PH2 pad43 enables low.\nDNP termination only after network topology review. EMC/ESD bench qualification pending.\nCAN2 and LIN2 use the comms2 sheet. PH2/PH3 GPIO additions are provisional schematic assignments.",25.4,175)
    can_tvs=box_symbol("PESD2CAN",[("1","CANH","passive",-10.16,5.08,0),("2","CANL","passive",-10.16,-5.08,0),("3","COMMON","passive",10.16,0,180)],
                       "Package_TO_SOT_SMD:SOT-23",prefix="D")
    comm.component(can_tvs,"D101","PESD2CAN",245,130,{"1":"CAN1_H","2":"CAN1_L","3":"GND"},note="Nexperia Rev2 pinning1/2lines3common; close connector; ground surge return review")
    lin=box_symbol("TLIN1029A_Q1",[("1","RXD","open_collector",-12.7,7.62,0),("4","TXD","input",-12.7,0,0),("2","EN","input",-12.7,-7.62,0),
                  ("6","LIN","bidirectional",12.7,0,180),("7","VSUP","power_in",0,15.24,270),("5","GND","power_in",0,-15.24,90),
                  ("3","NC","no_connect",12.7,7.62,180),("8","NC","no_connect",12.7,-7.62,180)],FP_SO8,width=20.32,height=25.4)
    comm.component(lin,"U104","TLIN1029ADRQ1",420,90,{"1":"LIN1_RX","4":"LIN1_TX","2":"LIN1_EN","6":"LIN1_BUS","7":"LIN1_VSUP","5":"GND"},
                   note="TI SLLSFK8A; 4..36V operating, 45V absolute VSUP; A variant avoids original duty-cycle erratum; default sleep")
    res(comm,"R107","4.7k",330,65,"+3V3","LIN1_RX","Open-drainRXD must never be pulled toVBAT/5V")
    res(comm,"R108","10k",330,115,"LIN1_EN","GND","Default sleep; MCU PH3 pad44 enables high")
    res(comm,"R109","0R DNP",330,165,"+3V3","LIN1_EN","Optionalnormalmode afterphysicalbusreview",dnp=True)
    res(comm,"R110","10k",375,165,"+3V3","LIN1_TX","Recessive input during MCUreset")
    res(comm,"R111","0R",420,165,"VBAT_LOGIC_PROTECTED","LIN1_VSUP","Requires root SMBJ24CA nominal38.9V clamp <45Vabs; actual pulse energy/overshoot gate remains")
    cap(comm,"C130","100n 50V X7R",465,165,"LIN1_VSUP","At U104 pin7")
    cap(comm,"C131","1u 50V X7R",510,165,"LIN1_VSUP",footprint="Capacitor_SMD:C_0805_2012Metric")
    cap(comm,"C132","1n 100V C0G",465,220,"LIN1_BUS","Commander bus capacitance; verify total cable/node capacitance")
    bas21=box_symbol("Core_BAS21",[("1","A","passive",-10.16,0,0),("3","K","passive",10.16,0,180),("2","NC","no_connect",0,-10.16,90)],"Package_TO_SOT_SMD:SOT-23",prefix="D")
    comm.component(bas21,"D102","BAS21,215",330,220,{"1":"LIN1_VSUP","3":"LIN1_COMMANDER_DIODE"},note="Commander assembly; remove D102 and R112 for responder-only topology")
    comm.component(r,"R112","1k 1% 0.5W",390,220,{"1":"LIN1_COMMANDER_DIODE","2":"LIN1_BUS"},footprint="Resistor_SMD:R_1206_3216Metric",note="16V dominant bound0.256W; pulse/voltage derating must be checked")
    comm.text("LIN1 commander assembly: MCU PH3 pad44 enables high; default sleep.\nOne commander per bus. Responder assembly omits BOTH D102/R112.\nVSUP4..36V operating,45V absolute. SMBJ24CA clamp38.9V is below absolute\nlimit, not proof of operation during transients or pulse qualification.",300,270)

    root.text("Power6GDI electrical candidate / NOT RELEASED\nConnected hierarchy: MCU, input supply, two GDI stages, safety, motor candidates, sensor frontends and harness.\nOutstanding channels and load qualification are tracked in INTEGRATION_2026_10_21_ELECTRICAL.md.",25.4,20)
    io_sheets=make_io(syms,ROOT_ID)
    output_sheets=make_outputs(syms,ROOT_ID)
    sheets.extend(io_sheets+output_sheets)
    from power_sources import make_sheet
    power_sources=make_sheet(ROOT_ID)
    sheets.append(power_sources)
    leaves=[mcu,comm]+ignition_sheets+io_sheets+output_sheets+[power_sources]
    external=[]
    for name,title,instance in [
        ("gdi/stage_a","GDI bank A reference candidate","a05bbd47-81aa-5269-b9b3-0a4b9afd615c"),
        ("gdi/stage_b","GDI bank B reference candidate","2aa9486d-083b-53a0-b9ea-735fb5a4b253"),
        ("safety/safety_gate","Latched hardware permission","d3688535-de83-5779-ad3b-0e54c99cc6b1"),
        ("board/connectors","Four TE34 harness connectors",None),
    ] + [(s['name'],s['title'],s['sheet_id']) for s in json.loads((HERE/'interfaces/interfaces_manifest.json').read_text())['sheets']] + [
        ('interfaces_aux/'+s['name'],s['name'].replace('_',' '),s['root_instance_uuid']) for s in json.loads((HERE/'interfaces_aux/interface.json').read_text())['sheets']
    ] + [
        (s['name'],s['name'].replace('_',' '),s['root_instance_uuid'])
        for s in json.loads((HERE/'gdi/protection_manifest.json').read_text())['sheets']
    ] + [
        (s['name'],s['name'].replace('_',' '),s['sheet_id'])
        for s in json.loads((HERE/'wbo/interface.json').read_text())['sheets']
    ] + [
        (s['name'],s['name'].replace('_',' '),s['root_instance_uuid'])
        for s in json.loads((HERE/'logic_power/interface.json').read_text())['sheets']
    ] + [
        (s['name'],s['name'].replace('_',' '),s['sheet_id'])
        for s in json.loads((HERE/'motor4/interface.json').read_text())['sheets']
    ]:
        if not (HERE/(name+".kicad_sch")).exists():
            raise FileNotFoundError("Integrated source-owned leaf required: "+name)
        leaf=Sheet(name,title,root=ROOT_ID)
        if instance: leaf.sheet_id=instance
        leaves.append(leaf)
        external.append({"path":name+".kicad_sch","instance_uuid":leaf.sheet_id})
    ports={mcu.name:[("+3V3","input"),("GND","input")],
           comm.name:[("+3V3","input"),("+5V_CORE","input"),("GND","input")]}
    for i,leaf in enumerate(leaves):
        title_size=min(3.81,148/max(1,len(leaf.title)))
        root.add_child(leaf,40+190*(i%6),65+75*(i//6),width=155,height=55,ports=ports.get(leaf.name,[]),title_size=title_size,file_size=2.54)
    root.text("Each sheet uses explicit global net names. HARNESS names remain separate from MCU logic.\nNo ERC exclusions. Power flags have explicit independently checked source paths. DNP assembly flags must be preserved.\nGDI enable, injector/pump models, missing domains and full routing remain release blockers.",25.4,745)
    for sheet in sheets: sheet.write(HERE)
    all_symbols={n:s for sheet in sheets for n,s in sheet.symbols.items()}
    for library in ["interfaces/interfaces.kicad_sym"]:
        source=parse((HERE/library).read_text(encoding="utf-8"))
        for expr in children(source,"symbol"):
            name=str(expr[1]).split(":")[-1]
            if name not in all_symbols:
                all_symbols[name]=Symbol(name,dump(expr))
    (HERE/"Power8GDI_Core.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+"\n".join(s.body.replace(q("Power8GDI_Core:"+s.name),q(s.name),1) for s in all_symbols.values())+')\n',encoding="utf-8")
    (HERE/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Core.kicad_sym")(options "")(descr "Source-derived Power8GDI core symbols")) (lib (name "Power8GDI_GDI")(type "KiCad")(uri "${KIPRJMOD}/gdi/Power8GDI_GDI.kicad_sym")(options "")(descr "GDI reference-derived symbols")))\n',encoding="utf-8")
    table=(HERE/"sym-lib-table").read_text(encoding="utf-8").rstrip()
    (HERE/"sym-lib-table").write_text(table[:-1]+' (lib (name "Power8GDI_Safety")(type "KiCad")(uri "${KIPRJMOD}/safety/Power8GDI_Safety.kicad_sym")(options "")(descr "Hardware permission candidate")))\n',encoding="utf-8")
    table=(HERE/"sym-lib-table").read_text(encoding="utf-8").rstrip()
    (HERE/"sym-lib-table").write_text(table[:-1]+' (lib (name "Power8GDI_Board")(type "KiCad")(uri "${KIPRJMOD}/board/Power8GDI_Board.kicad_sym")(options "")(descr "TE harness connectors")))\n',encoding="utf-8")
    table=(HERE/"sym-lib-table").read_text(encoding="utf-8").rstrip()
    (HERE/"sym-lib-table").write_text(table[:-1]+' (lib (name "Power8GDI_Aux")(type "KiCad")(uri "${KIPRJMOD}/interfaces_aux/Power8GDI_Aux.kicad_sym")(options "")(descr "Knock and wideband candidates")))\n',encoding="utf-8")
    (HERE/"Power8GDI_Core.kicad_pro").write_text('{"meta":{"filename":"Power8GDI_Core.kicad_pro","version":1}}\n',encoding="utf-8")
    for lib,relative in [('Power8GDI_GDIProtection','gdi/Power8GDI_GDIProtection'),('Power8GDI_WBO','wbo/Power8GDI_WBO'),('Power8GDI_LogicPower','logic_power/Power8GDI_LogicPower'),('Power8GDI_Motor4','motor4/Power8GDI_Motor4')]:
        table=(HERE/'sym-lib-table').read_text().rstrip()
        (HERE/'sym-lib-table').write_text(table[:-1]+f' (lib (name "{lib}")(type "KiCad")(uri "${{KIPRJMOD}}/{relative}.kicad_sym")(options "")(descr "Integrated reviewed source")))\n')
    footprint_dir=HERE/"Power8GDI_Core.pretty"
    footprint_dir.mkdir(exist_ok=True)
    pads=[]
    for n,x,y in [(1,-1.05,0.95),(2,1.05,0.95),(3,1.05,-0.95),(4,-1.05,-0.95)]:
        pads.append(f'(pad "{n}" smd rect (at {x} {y}) (size 0.9 0.9) (layers "F.Cu" "F.Paste" "F.Mask"))')
    (footprint_dir/"ASEM_3225.kicad_mod").write_text('(footprint "ASEM_3225" (version 20241229) (generator "pcbnew") (layer "F.Cu") (descr "Abracon ASEM RevP p4 land pattern; verification pending assembly review") (attr smd) (fp_text reference "REF**" (at 0 -2.2) (layer "F.SilkS") (effects (font (size 1 1)(thickness 0.15)))) (fp_text value "ASEM_3225" (at 0 2.2) (layer "F.Fab") (effects (font (size 1 1)(thickness 0.15)))) (fp_rect (start -1.6 -1.25)(end 1.6 1.25)(stroke (width 0.1)(type default))(fill none)(layer "F.Fab")) (fp_rect (start -1.85 -1.65)(end 1.85 1.65)(stroke (width 0.05)(type default))(fill none)(layer "F.CrtYd")) (fp_circle(center -1.5 1.6)(end -1.4 1.6)(stroke(width 0.15)(type default))(fill none)(layer "F.SilkS"))\n'+"\n".join(pads)+')\n',encoding="utf-8")
    (HERE/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Core.pretty")(options "")(descr "Source-derived core footprints")) (lib (name "Power8GDI_GDI")(type "KiCad")(uri "${KIPRJMOD}/gdi/Power8GDI_GDI.pretty")(options "")(descr "GDI source-derived footprints")))\n',encoding="utf-8")
    table=(HERE/"fp-lib-table").read_text(encoding="utf-8").rstrip()
    (HERE/"fp-lib-table").write_text(table[:-1]+' (lib (name "Power8GDI_Board")(type "KiCad")(uri "${KIPRJMOD}/board/Power8GDI_Board.pretty")(options "")(descr "TE34 land pattern candidate")))\n',encoding="utf-8")
    table=(HERE/"fp-lib-table").read_text(encoding="utf-8").rstrip()
    (HERE/"fp-lib-table").write_text(table[:-1]+' (lib (name "Power8GDI_Interfaces")(type "KiCad")(uri "${KIPRJMOD}/interfaces/Power8GDI_Interfaces.pretty")(options "")(descr "Interface source-derived footprints")))\n',encoding="utf-8")
    table=(HERE/'fp-lib-table').read_text().rstrip()
    (HERE/'fp-lib-table').write_text(table[:-1]+' (lib (name "Power8GDI_GDIProtection")(type "KiCad")(uri "${KIPRJMOD}/gdi/Power8GDI_GDIProtection.pretty")(options "")(descr "LM74800 floating exposed pad")))\n')
    table=(HERE/'fp-lib-table').read_text().rstrip()
    (HERE/'fp-lib-table').write_text(table[:-1]+' (lib (name "Power8GDI_Motor4")(type "KiCad")(uri "${KIPRJMOD}/motor4/Power8GDI_Motor4.pretty")(options "")(descr "Motor protection source footprint")))\n')
    manifest={"schema_version":1,"root_uuid":ROOT_ID,"project":"Power8GDI_Core","mcu":"STM32F767IIT6","qualification":"BLOCKED",
              "parts":[p for s in sheets for p in s.parts],"decoupling_placement":decoupling,"external_sheets":external,
              "added_gpio":[{"port":"PH2","pad":"43","net":"CAN1_STB","mode":"GPIO output; reset high-Z, external pullup"},{"port":"PH3","pad":"44","net":"LIN1_EN","mode":"GPIO output; reset high-Z, external pulldown"}],
              "mcu_pins":[{"pad":n,"name":p["name"],"net":nets.get(n)} for n,p in sorted(mcu_symbol.pins.items(),key=lambda x:int(x[0]))],
              "unassigned_functions":[x["function"] for x in gpio if x["stm32_pin"]=="UNASSIGNED"]}
    manifest["analog_channels"]=[dict(zip(["function","port","pad","adc"],row)) for row in ANALOG]
    (HERE/"core_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    with (HERE/"core_bom.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["ref","value","footprint","dnp","sheet","note"],extrasaction="ignore")
        writer.writeheader()
        writer.writerows(manifest["parts"])
    print(f"Generated {len(sheets)} sheets, {len(manifest['parts'])} components, all176 MCU pads accounted")


if __name__=="__main__": generate()
