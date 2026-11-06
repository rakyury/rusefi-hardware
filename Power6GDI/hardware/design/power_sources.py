"""Audited ERC source assertions across real passive/switching power paths.

PWR_FLAG models an external source or a power path through a diode, inductor,
resistor or controlled MOSFET that ERC cannot propagate through. It does not
assert regulation, startup success, current capability or hardware approval.
The same explicit path endpoints are checked independently in the XML export.
"""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
from core_schlib import Sheet, Symbol, q, uid, effect, num

HERE=Path(__file__).resolve().parent
# (net, explanation, required existing physical pin->net facts)
SOURCES=[
 ('GND','External battery return at harness; not a self-powered synthetic rail',{'J602.34':'GND'}),
 ('+5V_CORE','LM76003 SW output through L5200',{'U5200.1':'LP5_SW','L5200.1':'LP5_SW','L5200.2':'+5V_CORE'}),
 ('+3V3','TPS62130A SW output through L5300',{'U5300.1':'LP33_SW','L5300.1':'LP33_SW','L5300.2':'+3V3'}),
 ('+3V3_A','Main 3V3 through fitted R101 filter feed',{'R101.1':'+3V3','R101.2':'+3V3_A'}),
 ('VBAT_LOGIC_PROTECTED','Main externally fused input through series diode D5200',{'J602.33':'VBAT_MAIN_FUSED','D5200.3':'VBAT_MAIN_FUSED','D5200.2':'VBAT_LOGIC_PROTECTED'}),
 ('LIN1_VSUP','Protected battery through fitted 0R R111',{'R111.1':'VBAT_LOGIC_PROTECTED','R111.2':'LIN1_VSUP'}),
 ('LIN2_VSUP','Protected battery through fitted 0R R1506',{'R1506.1':'VBAT_LOGIC_PROTECTED','R1506.2':'LIN2_VSUP'}),
 ('SENSOR_A_IN','Protected battery through D1530, anode2 to cathode1',{'D1530.2':'VBAT_LOGIC_PROTECTED','D1530.1':'SENSOR_A_IN'}),
 ('SENSOR_B_IN','Protected battery through D1531, anode2 to cathode1',{'D1531.2':'VBAT_LOGIC_PROTECTED','D1531.1':'SENSOR_B_IN'}),
]
for stage,base,first in [('A',200,5001),('B',300,5051)]:
    p='PT'+stage
    SOURCES += [
      (f'GDI_{stage}_MID','Protected-input MOSFET midpoint; gate/state/thermal qualification is separate',
       {f'J601.{21 if stage=="A" else 23}':f'VBAT_GDI_{stage}_FUSED',f'Q{first}.3':f'VBAT_GDI_{stage}_FUSED',f'Q{first}.2':f'GDI_{stage}_MID'}),
      (f'VBAT_GDI_{stage}','Protected bank output through second MOSFET',
       {f'Q{first+1}.2':f'GDI_{stage}_MID',f'Q{first+1}.3':f'VBAT_GDI_{stage}'}),
      (p+'_VBOOST','Reference PT-controlled boost converter, rectifier cathode D12.2; not a guaranteed voltage',
       {f'L{base+1}.1':f'VBAT_GDI_{stage}',f'L{base+1}.2':p+'_+Batt_filtered',f'L{base+2}.1':p+'_+Batt_filtered',f'L{base+2}.2':p+'_Vdrive_coil',f'D{base+12}.1':p+'_Vdrive_coil',f'D{base+12}.2':p+'_VBOOST'}),
      (p+'_VCCIO','Main3V3 through fitted source sense resistor, power pads1/4',
       {f'R{base+21}.1':'+3V3',f'R{base+21}.4':p+'_VCCIO',f'U{base+1}.17':p+'_VCCIO'}),
    ]
for feed,base,raw in [('MOTOR13',6200,'VBAT_DBW_FUSED'),('MOTOR24',6250,'VBAT_EWG_FUSED')]:
    SOURCES += [
      (feed+'_MID','Motor protected-input MOSFET midpoint; dependent on enable',
       {f'J601.{33 if base==6200 else 34}':raw,f'Q{base}.3':raw,f'Q{base}.2':feed+'_MID'}),
      (feed+'_VS','Motor protected output through second MOSFET; dependent on enable',
       {f'Q{base+1}.2':feed+'_MID',f'Q{base+1}.3':feed+'_VS'}),
    ]


def make_sheet(root_id):
    s=Sheet('power_sources','Documented power sources across passive paths',root=root_id,paper='A2')
    body='''(symbol "Power8GDI_Core:Documented_PWR_FLAG" (power) (pin_names (offset 0)) (in_bom no) (on_board no)
      (property "Reference" "#FLG" (at 0 2.54 0) (effects (font (size 1 1)) (hide yes)))
      (property "Value" "PWR_FLAG" (at 0 5.08 0) (effects (font (size 1 1))))
      (symbol "Documented_PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 2.54) (xy -1.27 3.81) (xy 0 5.08) (xy 1.27 3.81) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "Documented_PWR_FLAG_1_1" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1 1)))) (number "1" (effects (font (size 1 1)))))))'''
    sym=Symbol('Documented_PWR_FLAG',body);s.symbols[sym.name]=sym
    s.text('Power assertions document EXISTING physical source paths; no ERC exclusions.\nEvery path below is checked against the exported real circuit. Voltage/current/startup qualification remains separate.',20,15)
    for i,(net,reason,_) in enumerate(SOURCES):
        x=25.4+(i%2)*270.51;y=45.72+(i//2)*29.21;ref=f'#FLG6{i:03}'
        s.items.append(f'(symbol (lib_id "Power8GDI_Core:Documented_PWR_FLAG") (at {num(x)} {num(y)} 0) (unit 1) (in_bom no) (on_board no) (dnp no) (uuid {q(s._id(ref))}) (property "Reference" {q(ref)} (at {num(x)} {num(y-6.35)} 0) {effect(hidden=True)}) (property "Value" "PWR_FLAG" (at {num(x)} {num(y-5.08)} 0) {effect()}) (pin "1" (uuid {q(s._id(ref+":1"))})) (instances (project "Power8GDI_Core" (path {q("/"+root_id+"/"+s.sheet_id)} (reference {q(ref)}) (unit 1)))))')
        s.label(net,x,y,global_=True);s.text(reason,x+10.16,y+2.54,.95)
    return s


def verify(path=HERE/'core.net'):
    root=ET.parse(path);parts={c.get('ref'):c for c in root.findall('components/comp')}
    pins={p.get('ref')+'.'+p.get('pin'):n.get('name') for n in root.findall('nets/net') for p in n.findall('node')}
    errors=[]
    for ref,value in {'R101':'0R','R111':'0R','R1506':'0R','R221':'0.01','R321':'0.01'}.items():
        if ref not in parts or parts[ref].findtext('value')!=value:errors.append(f'{ref}: source-path resistance changed; ERC assertion requires review')
    for net,reason,required in SOURCES:
        for pin,value in required.items():
            if pins.get(pin)!=value:errors.append(f'{net}: source path {pin} expected {value}, got {pins.get(pin)}')
            c=parts.get(pin.split('.')[0])
            if c is None or c.find('property[@name="dnp"]') is not None:errors.append(f'{net}: source part absent/DNP at {pin}')
    return {'status':'FAIL' if errors else 'PASS_DOCUMENTED_SOURCE_PATHS','source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'assertions':[{'net':n,'reason':r,'required_physical_connections':p} for n,r,p in SOURCES],
            'errors':errors,'qualification':'ERC semantics only; no power/thermal/startup guarantee'}


if __name__=='__main__':
    result=verify();(HERE/'power_source_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));raise SystemExit(bool(result['errors']))
