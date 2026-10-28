"""Reproducible electrical candidates. No ERC exclusions or invented power drivers."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DESIGN = HERE.parent
sys.path.insert(0, str(DESIGN))
from core_schlib import Sheet, Symbol, box_symbol, children, child, dump, parse, q, uid

ROOT = uid("Power8GDI_Core")
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SO8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
GPIO = [
    ("CAN2_RX", "PB5", 163, "AF9 CAN2_RX"),
    ("CAN2_TX", "PB6", 164, "AF9 CAN2_TX"),
    ("SENT3", "PE11", 74, "AF1 TIM1_CH2; relocate from PB6; shared timer with SENT1"),
    ("LIN2_TX", "PB10", 79, "AF7 USART3_TX"),
    ("LIN2_RX", "PB11", 80, "AF7 USART3_RX"),
    ("USB_DM", "PA11", 122, "AF10 OTG_FS_DM"),
    ("USB_DP", "PA12", 123, "AF10 OTG_FS_DP"),
    ("USB_VBUS_PRESENT_N", "PA9", 120, "GPIO input active low; native VBUS detection disabled"),
    ("SD_SPI3_SCK", "PC10", 139, "AF6 SPI3_SCK"),
    ("SD_SPI3_MISO", "PC11", 140, "AF6 SPI3_MISO"),
    ("SD_SPI3_MOSI", "PC12", 141, "AF6 SPI3_MOSI"),
    ("SD_CS", "PA8", 119, "GPIO output, default high"),
    ("SD_CD", "PG11", 154, "GPIO input polling, active low; not EXTI11"),
    ("CAN2_STB", "PG12", 155, "GPIO output, default high standby"),
    ("LIN2_EN", "PG13", 156, "GPIO output, default low sleep"),
    ("HALL1", "PH14", 129, "GPIO EXTI14; inverted"),
    ("HALL2", "PH15", 130, "GPIO EXTI15; inverted"),
    ("HALL3", "PI0", 131, "GPIO EXTI0; inverted"),
    ("HALL4", "PI7", 176, "GPIO EXTI7; inverted"),
    ("FLEX_FREQ", "PI8", 7, "GPIO EXTI8; inverted; timing not qualified"),
]
DIGITAL = ["HALL1", "HALL2", "HALL3", "HALL4", "FLEX_FREQ"]


def load_library(path):
    result = {}
    for expr in children(parse(path.read_text(encoding="utf-8")), "symbol"):
        name = str(expr[1]).split(":")[-1]
        # The embedded copy uses a full lib_id; disk libraries require bare names.
        expr[1] = type(expr[1])("Power8GDI_Core:" + name)
        props = {str(p[1]): str(p[2]) for p in children(expr, "property")}
        result[name] = Symbol(name, dump(expr), props.get("Footprint", ""))
    return result


def tracker_footprint():
    """TI DDA0008J-C02, 4231348/A p25: 5.4mm row span, 1.55x0.6 pads.

    Central copper 2.95x4.9; mask/paste opening 2.6x3.2. Repeated pad 9 is
    intentional; thermal vias are a board fabrication decision, not auto-filled.
    """
    directory = HERE / "Power8GDI_Interfaces.pretty"
    directory.mkdir(exist_ok=True)
    lines = ['(footprint "TPS7B4253_DDA0008J_C02" (version 20241229) (generator "pcbnew") (layer "F.Cu")',
             '(descr "TI TPS7B4253-Q1 SLVSCP3D DDA0008J-C02 4231348/A example land pattern; thermal vias required by board thermal review")',
             '(attr smd)',
             '(property "Reference" "REF**" (at 0 -3.3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "TPS7B4253QDDARQ1" (at 0 3.3) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -1.95 -2.45) (end 1.95 2.45) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
             '(fp_rect (start -3.73 -2.7) (end 3.73 2.7) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
             '(fp_circle (center -3 -2.65) (end -2.85 -2.65) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS"))']
    for n in range(1, 9):
        x = -2.7 if n <= 4 else 2.7
        y = -1.905 + (n-1)*1.27 if n <= 4 else 1.905-(n-5)*1.27
        lines.append(f'(pad "{n}" smd roundrect (at {x} {y:.3f}) (size 1.55 0.6) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.083333))')
    lines += ['(pad "9" smd rect (at 0 0) (size 2.95 4.9) (layers "F.Cu"))',
              '(pad "9" smd rect (at 0 0) (size 2.6 3.2) (layers "F.Cu" "F.Paste" "F.Mask"))', ')']
    (directory / "TPS7B4253_DDA0008J_C02.kicad_mod").write_text("\n".join(lines)+"\n", encoding="utf-8")


def generate():
    # TDK CGA9P3 2220 recommended a4.1..4.8 gap / b1.2..1.4 land /
    # c4.0..5.0 width. Generic KiCad2220 is wider and has too small a gap.
    directory=HERE/'Power8GDI_Interfaces.pretty';directory.mkdir(exist_ok=True)
    (directory/'CGA9P3_2220.kicad_mod').write_text('''(footprint "CGA9P3_2220" (version 20241229) (generator "pcbnew") (layer "F.Cu")
      (descr "TDK CGA9P3X7R1H226M250KB recommended range: gap4.5mm, lands1.3x4.5mm; assembly validation pending") (attr smd)
      (property "Reference" "REF**" (at 0 -3.4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
      (property "Value" "22u 50V X7R" (at 0 3.4) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
      (fp_rect (start -2.85 -2.5) (end 2.85 2.5) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_rect (start -3.8 -2.75) (end 3.8 2.75) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (pad "1" smd roundrect (at -2.9 0) (size 1.3 4.5) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1))
      (pad "2" smd roundrect (at 2.9 0) (size 1.3 4.5) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.1)))\n''',encoding='utf8')
    syms = load_library(DESIGN / "Power8GDI_Core.kicad_sym")
    syms.update(load_library(DESIGN / "power_input/power_input.kicad_sym"))
    sheets = []
    def sheet(name, title):
        s = Sheet("interfaces/"+name, title, root=ROOT, paper="A2")
        sheets.append(s)
        return s
    def r(s, n, value, x, y, a, b, footprint=FP_R, **kw):
        s.component(syms["R"], f"R{n}", value, x, y, {"1": a, "2": b}, footprint=footprint, **kw)
    def c(s, n, value, x, y, a, b="GND", footprint=FP_C, **kw):
        s.component(syms["C"], f"C{n}", value, x, y, {"1": a, "2": b}, footprint=footprint, **kw)
    comm = sheet("comms2", "CAN2 and LIN2 physical interfaces")
    comm.component(syms["TCAN1042HGV_Q1"], "U1501", "TCAN1042HGVDRQ1", 125, 90,
        {"1":"CAN2_TX", "4":"CAN2_RX", "8":"CAN2_STB", "7":"CAN2_H", "6":"CAN2_L", "3":"+5V_CORE", "5":"+3V3", "2":"GND"},
        note="TI SLLSES9D; STB pullup disables transmitter at MCU reset. PB5/PB6 AF9, PG12 standby.")
    c(comm,1501,"100n 16V X7R",205,65,"+5V_CORE", note="At U1501 pin3")
    c(comm,1502,"100n 16V X7R",260,65,"+3V3", note="At U1501 pin5")
    r(comm,1501,"10k",65,90,"+3V3","CAN2_STB")
    r(comm,1502,"120R DNP",205,130,"CAN2_H","CAN2_L",dnp=True,note="Only fit at a bus end after topology review")
    comm.component(syms["PESD2CAN"],"D1501","PESD2CAN",260,130,{"1":"CAN2_H","2":"CAN2_L","3":"GND"})
    comm.component(syms["TLIN1029A_Q1"],"U1502","TLIN1029ADRQ1",425,90,
        {"1":"LIN2_RX","4":"LIN2_TX","2":"LIN2_EN","6":"LIN2_BUS","7":"LIN2_VSUP","5":"GND"},
        note="TI SLLSFK8A A variant. VSUP 4..36V operating, 45V abs; pull-down EN gives sleep")
    r(comm,1503,"4.7k",335,65,"+3V3","LIN2_RX",note="RXD open-drain; pull only to3V3")
    r(comm,1504,"10k",335,130,"LIN2_EN","GND")
    r(comm,1505,"10k",390,165,"+3V3","LIN2_TX")
    r(comm,1506,"0R",445,165,"VBAT_LOGIC_PROTECTED","LIN2_VSUP",note="Requires root SMBJ24CA; 38.9V rated clamp is not pulse qualification")
    c(comm,1503,"100n 50V X7R",500,165,"LIN2_VSUP")
    c(comm,1504,"1u 50V X7R",500,225,"LIN2_VSUP",footprint="Capacitor_SMD:C_0805_2012Metric")
    c(comm,1505,"1n 100V C0G",445,225,"LIN2_BUS",note="Commander bus capacitance; verify total cable/node capacitance")
    bas21 = box_symbol("Interface_BAS21",[("1","A","passive",-10.16,0,0),("3","K","passive",10.16,0,180),("2","NC","no_connect",0,-10.16,90)],FP_SOT23,prefix="D")
    comm.component(bas21,"D1502","BAS21,215",355,230,{"1":"LIN2_VSUP","3":"LIN2_COMMANDER_DIODE"},note="Commander assembly: anode toward VSUP. Remove BOTH D1502/R1507 for responder-only harness topology")
    r(comm,1507,"1k 1% 0.5W",355,285,"LIN2_COMMANDER_DIODE","LIN2_BUS",footprint="Resistor_SMD:R_1206_3216Metric",note="0.256W upper bound at16V dominant; voltage/pulse derating remains required")
    comm.text("CAN2 default standby; LIN2 commander assembly, default sleep. MCU enables and schedules bus.\nOnly one commander pullup per LIN bus. Remove BOTH D1502/R1507 for responder-only assembly.\nCAN2 uses PB5/PB6; SENT3 uses PE11 pad74. Shared timer, CAN filters and firmware remain pending.\nNo automotive pulse/ESD/EMC or fault qualification is implied by this candidate.",25.4,335)

    esd = box_symbol("Interface_USBLC6_2SC6",[("1","IO1A","passive",-12.7,5.08,0),("6","IO1B","passive",12.7,5.08,180),
        ("3","IO2A","passive",-12.7,-5.08,0),("4","IO2B","passive",12.7,-5.08,180),
        ("5","VBUS","passive",0,15.24,270),("2","GND","passive",0,-15.24,90)],"Package_TO_SOT_SMD:SOT-23-6",width=20.32,height=25.4,prefix="D")
    usb = sheet("usb_fs", "Self-powered USB FS device: host VBUS never powers ECU")
    conn = box_symbol("Interface_USB_MicroB",[(str(n),name,"passive",-12.7,15.24-(n-1)*6.35,0) for n,name in enumerate(["VBUS","D-","D+","ID","GND","SHIELD"],1)],
        "Connector_USB:USB_Micro-B_Molex-105017-0001",width=20.32,height=40.64,prefix="J")
    usb.component(conn,"J1501","Molex 1050170001",100,90,{"1":"USB_HOST_VBUS","2":"USB_DM","3":"USB_DP","5":"GND","6":"USB_SHIELD"},
        note="Micro-B device-only; ID NC. Molex SD-105017-001 and official KiCad9 footprint; shell pads6. Not automotive/environmentally qualified")
    usb.component(esd,"D1510","USBLC6-2SC6",260,90,{"1":"USB_DP","6":"USB_DP","3":"USB_DM","4":"USB_DM","5":"USB_HOST_VBUS","2":"GND"},
        note="ST DS4260 Fig1: pins1/6 IO1,3/4 IO2,2GND,5VBUS. Close to connector with continuous GND return")
    c(usb,1510,"100n 16V X7R",350,90,"USB_HOST_VBUS")
    fet = box_symbol("Interface_2N7002",[("1","G","input",-12.7,0,0),("3","D","passive",12.7,7.62,180),("2","S","passive",12.7,-7.62,180)],FP_SOT23,width=20.32,height=20.32,prefix="Q")
    usb.component(fet,"Q1510","2N7002,215",260,220,{"1":"USB_VBUS_GATE","2":"GND","3":"USB_VBUS_PRESENT_N"},
        note="AN4879 MOSFET VBUS detector. MCU PA9 regular GPIO active-low; disables native OTG VBUS sensing; no5V on unpowered MCU")
    r(usb,1510,"1k",100,220,"USB_HOST_VBUS","USB_VBUS_GATE")
    r(usb,1511,"100k",170,220,"USB_VBUS_GATE","GND")
    r(usb,1512,"10k",350,220,"+3V3","USB_VBUS_PRESENT_N")
    r(usb,1513,"0R DNP",425,90,"USB_SHIELD","GND",dnp=True,note="Chassis/shield strategy and ground-loop/EMC review required before fit")
    c(usb,1511,"1n 2kV C0G",425,220,"USB_SHIELD",footprint="Capacitor_SMD:C_1812_4532Metric",note="C1812X102JGGACAUTO candidate; shield HF return, not isolation barrier; enclosure bonding review required")
    usb.text("Firmware: device-only mode, PA11/PA12 AF10, PA9 GPIO low=VBUS present; native VBUS detect disabled.\nNo external D+ pullup or series termination is fitted: STM32F767 FS PHY includes the required functions.\nHost VBUS feeds ESD reference and MOSFET gate ONLY; it must never be merged with +5V_CORE.\nUSB 48MHz clock, descriptors, attach/detach with ECU off, EMC and connector sealing remain unqualified.",25.4,315)

    sd = sheet("sd_spi", "microSD SPI3 logging candidate")
    sd_names = ["DAT2","DAT3_CS","CMD_MOSI","VDD","CLK","VSS","DAT0_MISO","DAT1","CD_SWITCH","CD_DETECT","SHELL"]
    sdconn=box_symbol("Interface_Molex104031",[(str(n),name,"passive",-15.24,31.75-(n-1)*6.35,0) for n,name in enumerate(sd_names,1)],
        "Connector_Card:microSD_HC_Molex_104031-0811",width=25.4,height=71.12,prefix="J")
    sd.component(sdconn,"J1502","Molex 1040310811",125,110,
        {"1":"SD_DAT2","2":"SD_CS","3":"SD_MOSI_CARD","4":"SD_3V3","5":"SD_SCK_CARD","6":"GND","7":"SD_SPI3_MISO","8":"SD_DAT1","9":"SD_CD","10":"GND","11":"GND"},
        note="Molex SD-104031-001: CD switch closes with card; official footprint numbers9/10 switch and11 shell. Card choice/load unspecified")
    r(sd,1520,"0R",65,225,"+3V3","SD_3V3",note="Current measurement link; no power switching or hot-plug inrush limit")
    c(sd,1520,"100n 16V X7R",125,225,"SD_3V3")
    c(sd,1521,"10u 16V X7R",185,225,"SD_3V3",footprint="Capacitor_SMD:C_0805_2012Metric")
    r(sd,1521,"22R",275,80,"SD_SPI3_SCK","SD_SCK_CARD",note="Provisional source series damping, tune only from SI evidence")
    r(sd,1522,"22R",335,80,"SD_SPI3_MOSI","SD_MOSI_CARD",note="Provisional source series damping")
    for i,net in enumerate(["SD_CS","SD_SPI3_MISO","SD_MOSI_CARD","SD_DAT1","SD_DAT2","SD_CD"]):
        r(sd,1523+i,"47k",260+(i%3)*75,150+(i//3)*75,"SD_3V3",net,note="SPI startup/unused data pullup; no clock pullup")
    c(sd,1522,"1n 16V X7R",475,225,"SD_CD",note="Card detect debounce is firmware polling, no EXTI reservation")
    for i,(a,b) in enumerate([("SD_SCK_CARD","SD_MOSI_CARD"),("SD_CS","SD_SPI3_MISO")]):
        sd.component(esd,f"D{1520+i}","USBLC6-2SC6",290+i*150,310,{"1":a,"6":a,"3":b,"4":b,"5":"SD_3V3","2":"GND"},
            note="ESD steering reference at3V3, below specified5.25V leakage test voltage; rail injection/clamping and actual system validation pending")
    sd.text("SPI mode only: PC10/11/12 AF6, PA8 chip select; PG11 card-detect polling, active low.\n3V3 card supply and MCU rail are shared. Card peak/write current, inrush, LDO thermal budget and power-fail data integrity are unknown.\nNo UHS/1.8V signaling, SDMMC or hot-plug qualification. Internal service socket: Molex -25..85C rating limits the assembly.",25.4,365)

    tracker_footprint()
    tracker = box_symbol("Interface_TPS7B4253DDA",[("8","IN","power_in",-15.24,10.16,0),("5","ADJ","input",-15.24,0,0),
        ("1","OUT","power_out",15.24,10.16,180),("4","FB","input",15.24,0,180),
        ("2","NC","no_connect",15.24,-10.16,180),("7","NC","no_connect",15.24,-17.78,180),
        ("3","GND3","power_in",-5.08,-25.4,90),("6","GND6","power_in",0,-25.4,90),("9","EP_GND","power_in",5.08,-25.4,90)],
        "Power8GDI_Interfaces:TPS7B4253_DDA0008J_C02",width=25.4,height=45.72)
    sp = sheet("sensor_power", "Dual sensor trackers and star returns")
    for i,bank in enumerate(["A","B"]):
        y=90+i*145; rail="SENSOR_5V_"+bank; vin="SENSOR_"+bank+"_IN"
        sp.component(syms["D_Schottky"],f"D{1530+i}","STPS2H100UY",85,y,{"1":vin,"2":"VBAT_LOGIC_PROTECTED"},footprint="Diode_SMD:D_SMB",
            note="Anode shared protected battery, cathode trackerIN. Isolates shared rail during TPS7B4253 short-to-battery detection latency")
        sp.component(tracker,f"U{1530+i}","TPS7B4253QDDARQ1",280,y,{"8":vin,"5":"+5V_CORE","1":rail,"4":rail,"3":"GND","6":"GND","9":"GND"},
            note="TI SLVSCP3D unity tracking. 300mA silicon rating is NOT permitted harness load. FB=OUT; ADJ draws <=5.5uA. EP copper+thermal vias review required")
        c(sp,1530+5*i,"1u 50V X7R",145,y,vin,footprint="Capacitor_SMD:C_0805_2012Metric")
        c(sp,1531+5*i,"100n 50V X7R",205,y,vin)
        c(sp,1532+5*i,"100n 16V X7R",205,y+60,"+5V_CORE",note="ADJ reference bypass close to pin5")
        c(sp,1533+5*i,"22u 50V X7R",390,y,rail,footprint="Power8GDI_Interfaces:CGA9P3_2220",
            note="CGA9P3X7R1H226M250KB candidate; effective >=10uF and ESR1mohm..20ohm remain qualification criteria;50V for short-to-battery")
        c(sp,1534+5*i,"100n 50V X7R",465,y,rail)
    for i,bank in enumerate(["A","B","C"]):
        sp.component(syms["R"],f"R{1530+i}","0R star return",100+i*160,315,
            {"1":"HARNESS_SENSOR_GND_"+bank,"2":"GND"},footprint="Resistor_SMD:R_0805_2012Metric",
            note="Dedicated sensor return link, local quiet-ground star. Current rating, ground offset and fault current/thermal coordination require review; not a fuse")
    sp.text("OUT=FB: unity tracking. ADJ reference+enable; no fault GPIO exists.\nInput/output abs45V: upstream clamp and cable-inductance overshoot tests required.\nAt14V/5V,100mA dissipates about0.9W per tracker;300mA about2.7W. Neither is a qualified load budget.\nGround return links are NOT fuses. Star placement, ground offset, thermal, cold crank and fault tests block release.",25.4,365)

    for group in range((len(DIGITAL)+5)//6):
        s=sheet(f"digital_aux_{group+1}",f"Additional Hall, flex and digital inputs bank {group+1}")
        nets={"14":"+3V3","7":"GND"}
        for j,(inp,out) in enumerate(zip([1,3,5,9,11,13],[2,4,6,8,10,12])):
            i=group*6+j
            if i >= len(DIGITAL):
                nets[str(inp)]="GND"
                continue
            name=DIGITAL[i]; filt=name+"_FILTERED"; y=65+j*48.26
            nets.update({str(inp):filt,str(out):name})
            r(s,1600+3*i,"10k",225,y,"HARNESS_"+name,filt,note="Current limit only, no automotive pulse rating claim")
            r(s,1601+3*i,"47k",285,y,filt,"GND")
            c(s,1600+i,"47p 100V C0G",345,y,filt,note="Nominal RC0.39us; actual source/cable/Schmitt delays require timing validation")
            s.component(syms["BAT54S"],f"D{1600+i}","BAT54S,215",405,y,{"1":"GND","2":"+5V_CORE","3":filt},note="Input5.5V tolerant; clamps can inject into5V rail. Unpowered simultaneous faults block release")
            r(s,1602+3*i,"10k DNP",475,y,"+5V_CORE","HARNESS_"+name,dnp=True,note="Optional open-drain sensor pullup; fit only after sensor/wiring review")
        s.component(syms["SN74LVC14A_Q1"],f"U{1600+group}","SN74LVC14AQPWRQ1",90,95,nets,note="2..3.6V supply,5.5V tolerant inputs, all channels INVERT. Unused inputsGND and outputsNC")
        c(s,1610+group,"100n 16V X7R",90,160,"+3V3")
        s.text("HALL1..4 and FLEX_FREQ use EXTI14/15/0/7/8. Former DIN5..8 connector sites are NC in the six-cylinder target.\nInput low/high thresholds, cable faults, power-off rail injection and flex frequency timing are not qualified.\nEvery active channel inverts. Optional open-drain pullups remain DNP until actual sensor models are known.",25.4,370)

    all_symbols={}
    for s in sheets:
        # A horizontal diode needs text above/below; the shared helper's passive
        # right-side anchors collide with its horizontal terminal and net label.
        for index, item in enumerate(s.items):
            if not item.startswith('(symbol (lib_id '):
                continue
            expr=parse(item)
            name=str(child(expr,'lib_id')[1]).split(':')[-1]
            symbol=s.symbols[name]
            if all(p['y']==0 and p['angle'] in (0,180) for p in symbol.pins.values()):
                at=child(expr,'at'); x,y=float(at[1]),float(at[2])
                for prop in children(expr,'property'):
                    if prop[1] in ('Reference','Value'):
                        position=child(prop,'at'); position[1:3]=[str(x),str(y+(-5.08 if prop[1]=='Reference' else 5.08))]
                        effects=child(prop,'effects'); effects[:]=[e for e in effects if not isinstance(e,list) or e[0]!='justify']
                s.items[index]=dump(expr)
            elif max(abs(p['y']) for p in symbol.pins.values())>=5 and any(p['angle']==90 for p in symbol.pins.values()):
                # Keep the value clear of a downward ground terminal/wire.
                at=child(expr,'at')
                prop=next(p for p in children(expr,'property') if p[1]=='Value')
                position=child(prop,'at');position[1]=str(float(at[1])+20.32)
                effects=child(prop,'effects');effects[:]=[e for e in effects if not isinstance(e,list) or e[0]!='justify']
                effects.append(['justify','left'])
                s.items[index]=dump(expr)
        s.write(DESIGN)
        all_symbols.update(s.symbols)
        (HERE/(s.name.split('/')[-1]+".kicad_pro")).write_text('{"meta":{"version":1},"erc":{"rule_severities":{}}}\n',encoding="utf-8")
    # Bare symbol names in the on-disk library. Do not copy the full core library.
    bodies=[]
    for name,symbol in sorted(all_symbols.items()):
        expr=parse(symbol.body); expr[1]=type(expr[1])(name); bodies.append(dump(expr))
    (HERE/"interfaces.kicad_sym").write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+"\n".join(bodies)+')\n',encoding="utf-8")
    (HERE/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Core") (type "KiCad") (uri "${KIPRJMOD}/interfaces.kicad_sym") (options "") (descr "Interface candidates")))\n',encoding="utf-8")
    (HERE/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "Power8GDI_Interfaces") (type "KiCad") (uri "${KIPRJMOD}/Power8GDI_Interfaces.pretty") (options "") (descr "TI DDA0008J-C02 land pattern")))\n',encoding="utf-8")
    parts=[p for s in sheets for p in s.parts]
    assert len({p['ref'] for p in parts})==len(parts)
    for s in sheets:
        for p in s.parts:
            symbol=next(x for x in s.symbols.values() if any(' (reference '+q(p['ref'])+')' in it and '(lib_id '+q('Power8GDI_Core:'+x.name)+')' in it for it in s.items))
            p['symbol']=symbol.name
            p['physical_pins']=sorted(symbol.pins,key=lambda n:int(n))
    manifest={"schema_version":1,"project":"Power8GDI_Core","root_uuid":ROOT,"qualification":"BLOCKED_ENGINEERING_CANDIDATE",
        "sheets":[{"name":s.name,"title":s.title,"uuid":s.uuid,"sheet_id":s.sheet_id} for s in sheets],
        "gpio_contract":[dict(zip(["function","stm32_pin","package_pad","mode"],row)) for row in GPIO],
        "harness_aliases":{"HARNESS_CAN2_H":"CAN2_H","HARNESS_CAN2_L":"CAN2_L","HARNESS_LIN2_BUS":"LIN2_BUS","HARNESS_SENSOR_5V_A":"SENSOR_5V_A","HARNESS_SENSOR_5V_B":"SENSOR_5V_B","HARNESS_CHASSIS_GND":"USB_SHIELD"},
        "digital_inverting_channels":DIGITAL,"parts":parts,"lin2_role":"commander assembly; default sleep",
        "blockers":["Firmware pinmux, USB VBUS GPIO/native detect and48MHz clock", "SD card peak current and3V3 LDO thermal budget", "Sensor load/thermal/dropout and effective capacitance", "Automotive transients, cable inductance, ESD, EMC and simultaneous unpowered faults", "Connector enclosure/sealing and shield bonding", "PCB connectivity/DRC/SI and hardware timing/fault measurements"]}
    (HERE/"interfaces_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    with (HERE/"interfaces_bom.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["ref","value","footprint","dnp","sheet","note"],extrasaction="ignore");writer.writeheader();writer.writerows(parts)
    print(f"Generated {len(sheets)} leaves, {len(parts)} physical components; release BLOCKED")


if __name__ == "__main__":
    generate()
