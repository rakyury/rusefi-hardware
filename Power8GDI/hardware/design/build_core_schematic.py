"""Generate the connected, explicitly unqualified Power8GDI core candidate."""
from __future__ import annotations
import csv
import json
from pathlib import Path

from core_schlib import Sheet, Symbol, box_symbol, child, children, dump, parse, q, uid

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
    root=Sheet("Power8GDI_Core","Power8GDI core and interfaces")
    mcu=Sheet("core_mcu","MCU, power decoupling and debug",root=ROOT_ID,paper="A2")
    power=Sheet("core_power","3V3 logic post-regulator",root=ROOT_ID)
    comm=Sheet("core_comms","CAN1 and LIN1 physical interfaces",root=ROOT_ID,paper="A2")
    ign=Sheet("core_ignition","Eight smart-coil logic candidates",root=ROOT_ID,paper="A2")
    sheets=[root,mcu,power,comm,ign]
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
            nets[n]=row["function"]
    for name,net in {"NRST":"NRST","BOOT0":"BOOT0","PA13":"SWDIO","PA14":"SWCLK","PB3":"SWO","PH0":"MCU_HSE_IN","PH2":"CAN1_STB","PH3":"LIN1_EN"}.items():
        n=pin_by_name[name]
        if n in nets: raise ValueError("Core pin already assigned: "+name)
        nets[n]=net
    mcu.hport("+3V3",25.4,25.4)
    mcu.hport("GND",25.4,33.02)
    mcu.component(mcu_symbol,"U101","STM32F767IIT6",152.4,177.8,nets,
                  note="Provisional industrial -40..85C LQFP176. Unassigned pads are intentionally unused in this candidate, not qualified resources.")
    mcu.text("176 physical pads; source: DS11532 Rev9 + official KiCad9.0.9 symbol.\nGPIO labels are logic-side draft functions, NEVER harness/actuator connections.\nNo USB or SD route is fitted. PH1, PC14/15 reserved unused; HSE bypass input only.",250,25.4)
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
    mcu.text("BLOCKED: independent kill/watchdog, crank/analog frontends, 26+ unmapped outputs/inputs.\nIGN1=PC13 remains draft: low-drive restrictions require high-impedance buffer.\nNo MCU output is connected directly to a coil, injector, solenoid or vehicle wire.",250,355)
    oscillator=box_symbol("ASEM1_8MHz",[("1","EN","input",-10.16,5.08,0),("3","OUT","output",10.16,0,180),
                         ("4","VDD","power_in",0,10.16,270),("2","GND","power_in",0,-10.16,90)],
                         "Power8GDI_Core:ASEM_3225",width=15.24,height=15.24,prefix="Y")
    mcu.component(oscillator,"Y101","ASEM1-8.000MHZ-LC-T",75,330,
                  {"1":"+3V3","2":"GND","3":"MCU_HSE_IN","4":"+3V3"},
                  note="Abracon ASEM RevP p4 actual pins1EN2GND3OUT4VDD; firmware HSE bypass required; PH1 NC")
    cap(mcu,"C129","10n 16V X7R",120,330,"+3V3","Abracon recommends10n between Y101 pins4/2; short return")
    mcu.text("8MHz CMOS HSE: bypass mode required.\nOscillator load <=15pF, start<=3ms.\nClock tree/USB48MHz firmware review pending.",25.4,365)

    ldo=box_symbol("TLV1117LV33DCY",[("3","IN","power_in",-10.16,5.08,0),("2","OUT_TAB","power_out",10.16,5.08,180),("1","GND","power_in",0,-10.16,90)],
                   "Package_TO_SOT_SMD:SOT-223-3_TabPin2",height=15.24)
    power.hport("+5V_CORE",25.4,25.4)
    power.hport("+3V3",25.4,33.02,"output")
    power.hport("GND",25.4,40.64)
    power.component(ldo,"U102","TLV1117LV33DCYR",120.65,76.2,{"3":"+5V_CORE","2":"+3V3","1":"GND"},note="TI SBVS160C; industrial candidate, not AEC-Q100; TAB=OUT pad2")
    cap(power,"C125","4.7u 16V X7R",65,76.2,"+5V_CORE","Effective CIN>=1uF; next to pin3")
    cap(power,"C126","4.7u 16V X7R",185,76.2,"+3V3","Effective COUT>=1uF; next to pad2; no reverse-power injection")
    power.text("Input: regulated +5V_CORE only, 5.5V maximum operating.\n1A silicon rating is NOT a thermal budget: at0.30A, (5-3.3)*0.30=0.51W.\nCopper/temperature/load budget remains BLOCKED. No raw VBAT connection.\nAll GPIO protection and GDI stage current are outside this 3V3 core regulator.",25.4,130)

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
    comm.text("CAN1_H/L are vehicle-side nets. STB high by default; MCU PH2 pad43 enables low.\nDNP termination only after network topology review. EMC/ESD bench qualification pending.\nCAN2 and LIN2 remain unassigned. PH2/PH3 GPIO additions are provisional schematic assignments.",25.4,175)
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
    cap(comm,"C132","220p 100V C0G",465,220,"LIN1_BUS","Respondermode buscap TI Fig10-1; busEMC/loadbudget pending")
    comm.text("LIN1 responder candidate: MCU PH3 pad44 enables high; default sleep.\nCommander role BLOCKED: requires1k + series diode pullup and network review.\nVSUP 4..36V operating,45V absolute. Requires root SMBJ24CA;38.9V specified clamp\nis below absolute limit, not proof of operation during transients or pulse qualification.",300,270)

    ign.hport("+5V_CORE",25.4,25.4)
    ign.hport("GND",25.4,33.02)
    driver=box_symbol("MIC4427YM",[("1","NC","no_connect",-12.7,7.62,0),("2","INA","input",-12.7,2.54,0),("4","INB","input",-12.7,-5.08,0),
                     ("7","OUTA","output",12.7,2.54,180),("5","OUTB","output",12.7,-5.08,180),("8","NC","no_connect",12.7,7.62,180),
                     ("6","VS","power_in",0,15.24,270),("3","GND","power_in",0,-15.24,90)],FP_SO8,width=20.32,height=25.4)
    for pair in range(4):
        a,b=2*pair+1,2*pair+2
        x=120+(pair%2)*260
        y=85+(pair//2)*170
        ign.component(driver,"U"+str(110+pair),"MIC4427YM",x,y,
                      {"2":f"IGN{a}","4":f"IGN{b}","7":f"IGN{a}_BUFFER","5":f"IGN{b}_BUFFER","6":"+5V_CORE","3":"GND"},
                      note="Non-inverting5V logicbuffer only; no coilprimary drive; no independentenable; outputlinksDNP")
        cap(ign,"C"+str(140+2*pair),"100n 16V X7R",x+65,y-30,"+5V_CORE","Close Udriver pin6/3")
        cap(ign,"C"+str(141+2*pair),"1u 16V X7R",x+110,y-30,"+5V_CORE")
        for index,channel in enumerate([a,b]):
            res(ign,"R"+str(120+channel-1),"100k",x-65,y-20+index*60,f"IGN{channel}","GND","Input defaultlow; PC13 load check includes inputI/C andtrace")
            res(ign,"R"+str(128+channel-1),"100R DNP",x+65,y+25+index*50,f"IGN{channel}_BUFFER",f"IGN{channel}_LOGIC_OUT",
                "Physical output remainsisolated until coilpolarity/load/current/faultkill reviewed",dnp=True)
            res(ign,"R"+str(136+channel-1),"100k",x+110,y+25+index*50,f"IGN{channel}_LOGIC_OUT","GND","Harnesslogic pulldown; no active drive with DNPserieslink")
    ign.text("All eight output series links R128..R135 are DNP: coil model, polarity, 5V current and independent kill unresolved.\nMIC4427 is a candidate buffer, not a qualified automotive ignition driver. No coils or loads may be attached.\nThe MCU-side names IGN1..8 are distinct from harness-side IGN1_LOGIC_OUT..8.\nPC13 load must remain below ST restrictions; MIC input typ6pF/max1uA, 100k pulldown adds33uA at3.3V.",25.4,375)

    root.text("Power8GDI electrical candidate / NOT RELEASED\nReal MCU/power/CAN connectivity; GDI and input protection integrated as separate source-owned sheets.\nMapped signal names denote 3V3 logic only. Unmapped channels and electrical frontends remain blocked.",25.4,20)
    root.add_child(power,60,65,ports=[("+5V_CORE","input"),("+3V3","output"),("GND","input")])
    root.add_child(mcu,180,65,ports=[("+3V3","input"),("GND","input")])
    root.add_child(comm,300,65,ports=[("+3V3","input"),("+5V_CORE","input"),("GND","input")])
    root.add_child(ign,180,165,ports=[("+5V_CORE","input"),("GND","input")])
    external=[]
    for name,title,x,y,instance in [
        ("power_input/power_input","Protected logic battery input",60,215,None),
        ("gdi/stage_a","GDI bank A reference candidate",300,165,"a05bbd47-81aa-5269-b9b3-0a4b9afd615c"),
        ("gdi/stage_b","GDI bank B reference candidate",300,225,"2aa9486d-083b-53a0-b9ea-735fb5a4b253"),
    ]:
        # These leaves are owned/generated by their specialists. Never rewrite them here.
        if not (HERE/(name+".kicad_sch")).exists():
            raise FileNotFoundError("Integrated source-owned leaf required: "+name)
        leaf=Sheet(name,title,root=ROOT_ID)
        if instance: leaf.sheet_id=instance
        root.add_child(leaf,x,y)
        external.append({"path":name+".kicad_sch","instance_uuid":leaf.sheet_id})
    root.text("Root supply port +5V_CORE requires root-owned power_input sheet.\nNo PWR_FLAG or ERC exclusion is added to conceal missing supply evidence.\nU101 unused pins are explicitly NC; these do not satisfy outstanding functional requirements.",25.4,135)
    for sheet in sheets: sheet.write(HERE)
    all_symbols={n:s for sheet in sheets for n,s in sheet.symbols.items()}
    source=parse((HERE/"power_input/power_input.kicad_sym").read_text(encoding="utf-8"))
    for expr in children(source,"symbol"):
        name=str(expr[1]).split(":")[-1]
        if name not in all_symbols:
            all_symbols[name]=Symbol(name,dump(expr))
    (HERE/"Power8GDI_Core.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+"\n".join(s.body.replace(q("Power8GDI_Core:"+s.name),q(s.name),1) for s in all_symbols.values())+')\n',encoding="utf-8")
    (HERE/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Core.kicad_sym")(options "")(descr "Source-derived Power8GDI core symbols")) (lib (name "Power8GDI_GDI")(type "KiCad")(uri "${KIPRJMOD}/gdi/Power8GDI_GDI.kicad_sym")(options "")(descr "GDI reference-derived symbols")))\n',encoding="utf-8")
    (HERE/"Power8GDI_Core.kicad_pro").write_text('{"meta":{"filename":"Power8GDI_Core.kicad_pro","version":1}}\n',encoding="utf-8")
    footprint_dir=HERE/"Power8GDI_Core.pretty"
    footprint_dir.mkdir(exist_ok=True)
    pads=[]
    for n,x,y in [(1,-1.05,0.95),(2,1.05,0.95),(3,1.05,-0.95),(4,-1.05,-0.95)]:
        pads.append(f'(pad "{n}" smd rect (at {x} {y}) (size 0.9 0.9) (layers "F.Cu" "F.Paste" "F.Mask"))')
    (footprint_dir/"ASEM_3225.kicad_mod").write_text('(footprint "ASEM_3225" (version 20241229) (generator "pcbnew") (layer "F.Cu") (descr "Abracon ASEM RevP p4 land pattern; verification pending assembly review") (attr smd) (fp_text reference "REF**" (at 0 -2.2) (layer "F.SilkS") (effects (font (size 1 1)(thickness 0.15)))) (fp_text value "ASEM_3225" (at 0 2.2) (layer "F.Fab") (effects (font (size 1 1)(thickness 0.15)))) (fp_rect (start -1.6 -1.25)(end 1.6 1.25)(stroke (width 0.1)(type default))(fill none)(layer "F.Fab")) (fp_rect (start -1.85 -1.65)(end 1.85 1.65)(stroke (width 0.05)(type default))(fill none)(layer "F.CrtYd")) (fp_circle(center -1.5 1.6)(end -1.4 1.6)(stroke(width 0.15)(type default))(fill none)(layer "F.SilkS"))\n'+"\n".join(pads)+')\n',encoding="utf-8")
    (HERE/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Core.pretty")(options "")(descr "Source-derived core footprints")) (lib (name "Power8GDI_GDI")(type "KiCad")(uri "${KIPRJMOD}/gdi/Power8GDI_GDI.pretty")(options "")(descr "GDI source-derived footprints")))\n',encoding="utf-8")
    manifest={"schema_version":1,"root_uuid":ROOT_ID,"project":"Power8GDI_Core","mcu":"STM32F767IIT6","qualification":"BLOCKED",
              "parts":[p for s in sheets for p in s.parts],"decoupling_placement":decoupling,"external_sheets":external,
              "added_gpio":[{"port":"PH2","pad":"43","net":"CAN1_STB","mode":"GPIO output; reset high-Z, external pullup"},{"port":"PH3","pad":"44","net":"LIN1_EN","mode":"GPIO output; reset high-Z, external pulldown"}],
              "mcu_pins":[{"pad":n,"name":p["name"],"net":nets.get(n)} for n,p in sorted(mcu_symbol.pins.items(),key=lambda x:int(x[0]))],
              "unassigned_functions":[x["function"] for x in gpio if x["stm32_pin"]=="UNASSIGNED"]}
    (HERE/"core_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    with (HERE/"core_bom.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["ref","value","footprint","dnp","sheet","note"],extrasaction="ignore")
        writer.writeheader()
        writer.writerows(manifest["parts"])
    print(f"Generated {len(sheets)} sheets, {len(manifest['parts'])} components, all176 MCU pads accounted")


if __name__=="__main__": generate()
