"""Source-derived analog, Hall/SENT and differential VR receiver candidates."""
from core_schlib import Sheet,box_symbol

ANALOG=[
 ("TPS1","PA0","40","ADC1_IN0"),("TPS2","PA2","42","ADC1_IN2"),
 ("PPS1","PA3","47","ADC1_IN3"),("PPS2","PA4","50","ADC1_IN4"),
 ("MAP_MAIN","PA5","51","ADC1_IN5"),("BARO_EXT","PA6","52","ADC1_IN6"),
 ("CLT","PA7","53","ADC1_IN7"),("IAT","PB0","56","ADC1_IN8"),
 ("OIL_PRESS","PC0","32","ADC1_IN10"),("OIL_TEMP","PC1","33","ADC1_IN11"),
 ("FRP1","PC2","34","ADC1_IN12"),("FRP2","PC3","35","ADC1_IN13"),
 ("LPFP_PRESS","PC4","54","ADC1_IN14"),("EXH_PRESS","PC5","55","ADC1_IN15"),
 ("EWG_POS","PF6","24","ADC3_IN4"),("AUX_ANALOG1","PF10","28","ADC3_IN8"),
 ("AUX_ANALOG2","PF8","26","ADC3_IN6"),
]
DIGITAL=["CAM1","CAM2","CAM3","CAM4","SENT1","SENT2","SENT3","SENT4"]
FP_R="Resistor_SMD:R_0603_1608Metric"
FP_C="Capacitor_SMD:C_0603_1608Metric"
FP_TSSOP="Package_SO:TSSOP-14_4.4x5mm_P0.65mm"


def make_io(syms,root_id):
    sheets=[]
    r,c=syms["R"],syms["C"]
    def resistor(sheet,ref,value,x,y,a,b,**kw):
        sheet.component(r,ref,value,x,y,{"1":a,"2":b},footprint=FP_R,**kw)
    def cap(sheet,ref,value,x,y,a,b="GND",**kw):
        sheet.component(c,ref,value,x,y,{"1":a,"2":b},footprint=FP_C,**kw)
    clamp=box_symbol("BAT54S",[("1","A1","passive",0,-10.16,90),("2","K2","passive",0,10.16,270),
                    ("3","K1_A2","passive",-10.16,0,0)],"Package_TO_SOT_SMD:SOT-23",prefix="D")
    # Pin numbers are from TI SBOS980G Fig5-4/Table5-3, not package-order inference.
    plus=[3,5,10,12]; minus=[2,6,9,13]; outs=[1,7,8,14]
    pins=[("4","V+","power_in",0,27.94,270),("11","V-","power_in",0,-27.94,90)]
    for j in range(4):
        pins.extend([(str(plus[j]),f"IN{j+1}+","input",-20.32,20.32-j*10.16,0),
                     (str(minus[j]),f"IN{j+1}-","input",-20.32,15.24-j*10.16,0),
                     (str(outs[j]),f"OUT{j+1}","output",20.32,17.78-j*10.16,180)])
    opamp=box_symbol("TLV9004_Q1",pins,FP_TSSOP,width=35.56,height=50.8)
    for group in range(5):
        sheet=Sheet(f"io/analog_{group+1}",f"Buffered analog inputs {group*4+1}..{min(17,group*4+4)}",root=root_id,paper="A2")
        sheets.append(sheet)
        nets={"4":"+3V3_A","11":"GND"}
        for j in range(4):
            i=group*4+j
            if i>=len(ANALOG):
                net=f"ADC_UNUSED_{i+1}"
                nets.update({str(plus[j]):"GND",str(minus[j]):net,str(outs[j]):net})
                continue
            name,port,pad,adc=ANALOG[i]
            div=f"{name}_DIV"; buffered=f"{name}_BUFFER"; output=f"ADC_{name}"
            nets.update({str(plus[j]):div,str(minus[j]):buffered,str(outs[j]):buffered})
            y=65+j*76.2
            sheet.text(f"{name}: {port} pad{pad} / {adc}; normal input 0..5.5V",210,y-27.94)
            resistor(sheet,f"R{700+3*i}","100k 0.1%",220,y,"HARNESS_"+name,div,note="Input current limiter; 0603 working/pulse voltage and fault energy must be qualified")
            resistor(sheet,f"R{701+3*i}","100k 0.1%",275,y,div,"GND")
            cap(sheet,f"C{700+2*i}","1n 50V C0G",330,y,div,note="100k||100k and1n: nominal3.18kHz pole; source impedance changes transfer")
            sheet.component(clamp,f"D{701+i}","BAT54S,215",385,y,{"1":"GND","2":"+3V3_A","3":div},
                            note="Pin1=A1,2=K2,3=series midpoint. Clamp injection/backpower and hot leakage not qualified")
            resistor(sheet,f"R{702+3*i}","1k",440,y,buffered,output,note="Isolates opamp from ADC sampling capacitor; settling budget pending")
            cap(sheet,f"C{701+2*i}","10n 16V X7R",495,y,output)
        sheet.component(opamp,f"U{701+group}","TLV9004QPWRQ1",90,100,nets,
                        note="Unity-gain followers; spare amplifiers tied toGND with closed feedback. 1.8..5.5V supply")
        cap(sheet,f"C{740+2*group}","100n 16V X7R",65,175,"+3V3_A")
        cap(sheet,f"C{741+2*group}","1u 16V X7R",120,175,"+3V3_A")
        sheet.text("Nominal gain0.5; use2x voltage scaling in calibration.\nRC, opamp offset, diode leakage, ADC sample time and reference error require analysis.\nFault clamps inject into3V3 rail: power-off/backfeed and simultaneous fault tests BLOCK RELEASE.\nThese are candidates for 0..5V sensors; no raw battery input or load may be connected.",25.4,345)
    # Optional NTC bias needs the actual sensor resistance curve and wiring fault review.
    for i,name in enumerate(["CLT","IAT","OIL_TEMP"]):
        resistor(sheets[4],f"R{751+i}","2.49k DNP",230+i*100,190,"+5V_CORE","HARNESS_"+name,
                 dnp=True,note="Optional NTC bias. Fit only after sensor curve, supply/reference and short-to-battery review")

    in_pads=[1,3,5,9,11,13]; out_pads=[2,4,6,8,10,12]
    pins=[("14","VCC","power_in",0,25.4,270),("7","GND","power_in",0,-25.4,90)]
    for j in range(6):
        pins += [(str(in_pads[j]),f"{j+1}A","input",-15.24,19.05-j*7.62,0),
                 (str(out_pads[j]),f"{j+1}Y_INV","output",15.24,19.05-j*7.62,180)]
    schmitt=box_symbol("SN74LVC14A_Q1",pins,FP_TSSOP,width=25.4,height=45.72)
    for group in range(2):
        sheet=Sheet(f"io/digital_{group+1}",f"Hall and SENT receiver bank {group+1}",root=root_id,paper="A2")
        sheets.append(sheet)
        nets={"14":"+3V3","7":"GND"}
        for j in range(6):
            i=group*6+j
            if i>=len(DIGITAL):
                nets[str(in_pads[j])]="GND"
                continue
            name=DIGITAL[i]; filt=name+"_FILTERED"
            nets.update({str(in_pads[j]):filt,str(out_pads[j]):name})
            y=65+j*48.26
            sheet.text(name+": INVERTED at MCU; firmware edge/idle polarity required",210,y-20.32)
            resistor(sheet,f"R{760+3*i}","10k",225,y,"HARNESS_"+name,filt,note="Series current limiting; no automotive pulse qualification")
            resistor(sheet,f"R{761+3*i}","47k",285,y,filt,"GND")
            cap(sheet,f"C{750+i}","47p 100V C0G",345,y,filt,note="Nominal inputRC0.39us; SENT cable/pulse-width distortion must be measured")
            sheet.component(clamp,f"D{730+i}","BAT54S,215",405,y,{"1":"GND","2":"+5V_CORE","3":filt},
                            note="Clamp to5V because LVC input is5.5V tolerant. Power-off rail injection is unqualified")
            resistor(sheet,f"R{762+3*i}","10k DNP",475,y,"+5V_CORE","HARNESS_"+name,dnp=True,
                     note="Optional open-drain sensor pullup; sensor model and short-to-battery behavior required")
        sheet.component(schmitt,f"U{721+group}","SN74LVC14AQPWRQ1",90,95,nets,
                        note="Hex inverter,2..3.6V supply,5.5V tolerant inputs; unused inputsGND, outputsNC")
        cap(sheet,f"C{758+group}","100n 16V X7R",90,160,"+3V3")
        sheet.text("Hall/push-pull5V candidate only; CAM VR sensors require a different differential frontend.\nOptional pullups DNP until sensor model confirmed. Every channel INVERTS.\nSENT timing, input thresholds, clamp injection, cables and EMC remain unqualified.",25.4,370)

    vr=Sheet("io/crank_vr","Differential VR crank receiver",root=root_id)
    sheets.append(vr)
    pins=[("1","IN+","input",-15.24,12.7,0),("2","IN-","input",-15.24,5.08,0),
          ("3","NC","no_connect",15.24,-15.24,180),("4","BIAS","input",-15.24,-2.54,0),
          ("5","GND","power_in",0,-22.86,90),("6","ZERO_EN","input",-15.24,-10.16,0),
          ("7","COUT","open_collector",15.24,7.62,180),("8","EXT","input",15.24,-7.62,180),
          ("9","INT_THRS","input",-15.24,-17.78,0),("10","VCC","power_in",0,22.86,270)]
    max9924=box_symbol("MAX9924UAUB",pins,"Package_SO:MSOP-10_3x3mm_P0.5mm",width=25.4,height=40.64)
    vr.component(max9924,"U731","MAX9924UAUB/V+",190,85,{"1":"VR_CRANK_P_FILT","2":"VR_CRANK_N_FILT","4":"GND","5":"GND","6":"GND","7":"CRANK","9":"GND","10":"+5V_CORE"},
                 note="Rev5 Table1 ModeA2: ZERO_EN=GND,INT_THRS=GND,BIAS=GND; EXT NC. Do not infer from mode pin names")
    resistor(vr,"R790","10k 0.1%",65,65,"HARNESS_CRANK_VR_P","VR_CRANK_P_FILT")
    resistor(vr,"R791","10k 0.1%",110,65,"HARNESS_CRANK_VR_N","VR_CRANK_N_FILT")
    cap(vr,"C760","1n 100V C0G",65,135,"VR_CRANK_P_FILT","VR_CRANK_N_FILT",note="Differential filter from manufacturerFig3; actual tooth amplitude/frequency pending")
    resistor(vr,"R792","10k",280,85,"+3V3","CRANK",note="Open-drain output toMCU3V3, never5V")
    cap(vr,"C761","100n 16V X7R",280,145,"+5V_CORE")
    cap(vr,"C762","1u 16V X7R",330,145,"+5V_CORE")
    vr.text("ModeA2: internal bias, adaptive threshold and zero-crossing enabled.\nSupply4.5..5.5V; input absolute current +/-40mA is NOT an operating/protection target.\n10k input resistors/filter are a reference-derived starting point; VR amplitude,\nresistor pulse rating, cranking sensitivity, tooth polarity and EMI require bench review.\nPB1 uses EXTI1 with scheduler timestamp: not a TIM3 capture channel shared with motors.",25.4,205)
    return sheets
