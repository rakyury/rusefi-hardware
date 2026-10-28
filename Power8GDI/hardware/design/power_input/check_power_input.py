"""Independent checks of the actual KiCad-exported supply network."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
root=ET.parse(HERE/'power_input.xml').getroot()
nets={n.attrib['name']:{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')} for n in root.findall('./nets/net')}
pin_net={p:name for name,pins in nets.items() for p in pins}
checked=[]
def connection(ref,pin,net):
    assert pin_net.get((ref,str(pin)))==net,(ref,pin,net,pin_net.get((ref,str(pin))))
    checked.append((ref,pin,net))
for ref,pin,net in [('D501',1,'VBAT_LOGIC_PROTECTED'),('D501',2,'VBAT_MAIN_FUSED'),
                    ('U501',1,'GND'),('U501',9,'GND'),('U501',2,'VBAT_LOGIC_PROTECTED'),
                    ('U501',7,'BUCK_BST'),('U501',8,'BUCK_SW'),('U501',5,'BUCK_FB'),
                    ('C504',1,'BUCK_BST'),('C504',2,'BUCK_SW'),
                    ('L501',1,'BUCK_SW'),('L501',2,'+5V_CORE'),
                    ('R506',1,'BUCK_SW'),('R506',2,'BUCK_RIPPLE'),
                    ('C507',1,'BUCK_RIPPLE'),('C507',2,'+5V_CORE'),
                    ('C508',1,'BUCK_RIPPLE'),('C508',2,'BUCK_FB'),
                    ('R504',1,'+5V_CORE'),('R504',2,'BUCK_FB'),
                    ('R505',1,'BUCK_FB'),('R505',2,'GND'),
                    ('R507',1,'+3V3'),('R507',2,'PGOOD_5V_CORE')]:
    connection(ref,pin,net)
assert len(root.findall('./components/comp'))==19
assert not any('GDI' in name for name in nets), 'Actuator supply leaked into logic regulator'
values={c.attrib['ref']:c.findtext('value') for c in root.findall('./components/comp')}
assert values['R506']=='110k 1%'
# Recompute from chosen values rather than accepting generated PASS fields.
vo=1.2*(1+158/49.9); fs=vo*2500/41.2*1000
for vi in (8.295,12,16,24,53.3):
    ripple=vo/fs/(47e-6*.8)*(1-vo/vi)
    assert .8+ripple/2<1.25, 'Peak limit margin exhausted at minimum L'
vfall=1.35*(1+453*.99/(100*1.01))
injection=(vo/vfall/fs)*(vfall-vo)/(110e3*3.3e-9)
assert injection>0.012, 'Nominal injection inadequate near lowest UVLO threshold'
assert 2.2e-9*.95>1.5e-9 and 2.2e-9*1.05<2.5e-9
result={'result':'PASS_CONNECTIVITY_AND_NOMINAL_CALCULATIONS_ONLY','components':19,
        'critical_connections_checked':len(checked),'nominal_injection_at_min_uvlo_mv':injection*1000,
        'manufacturing_release':False,'note':'IC timing tolerances, actual load, thermal and transient tests remain open'}
(HERE/'power_input_checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
