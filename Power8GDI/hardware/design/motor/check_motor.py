"""Evaluate the actual exported gating network and power paths, not a drawing."""
from pathlib import Path
import itertools
import json
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
def read(channel):
    root=ET.parse(HERE/(channel.lower()+'_driver.xml')).getroot()
    parts={c.attrib['ref']:{'value':c.findtext('value'),'pins':{}} for c in root.findall('./components/comp')}
    for net in root.findall('./nets/net'):
        for node in net.findall('node'):
            parts[node.attrib['ref']]['pins'][node.attrib['pin']]=net.attrib['name']
    return parts

def evaluate(parts,state):
    state=dict(state);pending={r:p for r,p in parts.items() if p['value'].startswith('SN74LVC1G')}
    while pending:
        progressed=False
        for ref,part in list(pending.items()):
            pins=part['pins'];is_and='1G08' in part['value'];inputs=('1','2') if is_and else ('2',)
            if all(pins[p] in state for p in inputs):
                state[pins['4']]=all(state[pins[p]] for p in inputs) if is_and else not state[pins['2']]
                del pending[ref];progressed=True
        assert progressed, f'Unresolved/cyclic gating network: {list(pending)}'
    return state

results={}
for ch,base in [('DBW',900),('EWG',950)]:
    parts=read(ch);pre=ch+'_';u=parts['U'+str(base+1)]['pins']
    assert len(parts)==25
    for pin,net in [('5',pre+'VM'),('6',pre+'MOTOR_A'),('8',pre+'MOTOR_B'),('1','GND'),('7','GND'),('9','GND'),('4',pre+'ILIM')]:
        assert u[pin]==net,(ch,pin,net,u[pin])
    assert parts['D'+str(base+1)]['pins']=={'1':pre+'VM','2':'VBAT_'+ch+'_FUSED'}
    assert parts['D'+str(base+2)]['pins']=={'1':pre+'VM','2':'GND'}, 'TVS must catch regeneration after reverse diode'
    for number in (6,7):
        r=parts['R'+str(base+number)]
        assert r['value']=='10k'
        assert r['pins']['2']=='GND'
    assert 11e-6*10000*1.01 < .5, 'Poweroff leakage can violate DRV input-low guarantee'
    assert parts['R'+str(base+4)]['pins']=={'1':'+3V3','2':pre+'DISABLE'}
    assert parts['R'+str(base+1)]['value']=='36.5k 1%'
    assert parts['R'+str(base+1)]['pins']=={'1':pre+'ILIM','2':'GND'}
    cases=0
    for pwm,direction,disable,permission in itertools.product((False,True),repeat=4):
        inputs={pre+'PWM':pwm,pre+'DIR':direction,pre+'DISABLE':disable,'HW_ACTUATOR_ENABLE':permission}
        state=evaluate(parts,inputs);on=pwm and permission and not disable
        expected=(on and not direction,on and direction)
        actual=(state[u['3']],state[u['2']])
        assert actual==expected,(ch,inputs,expected,actual)
        cases+=1
    # Prove the checker sees loss of the independent hardware inhibit.
    altered={r:{'value':p['value'],'pins':dict(p['pins'])} for r,p in parts.items()}
    altered['U'+str(base+10)]['pins']['1']='+3V3'
    state=evaluate(altered,{pre+'PWM':True,pre+'DIR':False,pre+'DISABLE':False,'HW_ACTUATOR_ENABLE':False,'+3V3':True})
    assert state[u['3']] is True, 'Mutation did not expose bypassed hardware inhibit'
    results[ch]={'components':len(parts),'truth_cases':cases,'power_paths':'PASS','hardware_inhibit_bypass_mutation_detected':True}
report={'status':'PASS_STATIC_NETWORK_AND_NOMINAL_CALCULATIONS','channels':results,
        'current_limit_calculated_a':{'minimum':59/(36.5*1.01),'nominal':64/36.5,'maximum':69/(36.5*.99)},
        'release':'BLOCKED','hardware_tested':False,'motor_models':None}
(HERE/'motor_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
