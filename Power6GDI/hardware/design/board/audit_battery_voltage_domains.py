"""Discover protected battery, floating gate/charge-pump and motor-output nets.

The 0.3 mm target is the existing project battery policy, not certification.
Actual XML pin roles are checked; low-voltage control names are not guessed.
"""
from collections import defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCES={
 'LM74800':'https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf',
 'TLE9201':'https://www.infineon.com/dgdl/Infineon-TLE9201SG-DS-v01_00-en.pdf?fileId=db3a304345087709014518190f481cec',
}
LM_PINS={'1':'DGATE','2':'A','3':'VSNS','4':'SW','8':'HGATE','9':'OUT','10':'VS','11':'CAP','12':'C','13':'EP_FLOAT'}
BRIDGE_PINS={'4':'VS','5':'OUT1','7':'OUT2'}


def discover(netlist):
    root=ET.parse(netlist)
    parts={c.get('ref'):c.findtext('value') for c in root.findall('components/comp')}
    nets={n.get('name'):[dict(x.attrib) for x in n.findall('node')] for n in root.findall('nets/net')}
    bypin={(x['ref'],x['pin']):(name,x) for name,nodes in nets.items() for x in nodes}
    byref=defaultdict(set)
    for (ref,pin),(name,node) in bypin.items():byref[ref].add(name)
    reasons=defaultdict(set);gate_seeds=set()
    for refs,value,pins in [
      (('U5001','U5051','U6200','U6250'),'LM74800QDRRRQ1',LM_PINS),
      (('U6000','U6050'),'TLE9201SG',BRIDGE_PINS),
    ]:
        for ref in refs:
            if parts.get(ref)!=value:raise ValueError(f'{ref}: device changed; voltage-domain review required')
            for pin,role in pins.items():
                name,node=bypin[(ref,pin)]
                if node.get('pinfunction')!=role:raise ValueError(f'{ref}.{pin}: expected {role}; got {node}')
                if name=='GND' or name.startswith(('+3V3','+5V')):
                    raise ValueError(f'{ref}.{pin}: unexpected battery-domain tie to {name}')
                if role=='EP_FLOAT' and len(nets[name])!=1:
                    raise ValueError(f'{ref}: exposed pad must remain electrically floating')
                reasons[name].add(f'{ref}.{pin} {role}')
                if role in ('DGATE','HGATE'):gate_seeds.add(name)
    # One series-gate-resistor hop; never follow SW's OV divider into logic.
    for name in sorted(gate_seeds):
        for node in nets[name]:
            ref=node['ref']
            if ref.startswith('R') and len(byref[ref])==2:
                for other in byref[ref]-{name}:
                    if other=='GND' or other.startswith(('+3V3','+5V')):
                        raise ValueError(f'{ref}: unexpected gate-domain tie to {other}')
                    reasons[other].add(f'One series resistor {ref} from {name}')
    return {n:{'evidence':sorted(r),'nodes':nets[n]} for n,r in sorted(reasons.items())}


def report(netlist):
    domains=discover(netlist)
    return {'netlist_sha256':hashlib.sha256(Path(netlist).read_bytes()).hexdigest(),
      'sources':SOURCES,'candidate_clearance_mm':.3,'discovered_net_count':len(domains),
      'interpretation':'LM74800 Table6-1/7-1 and9.3: CAP and gate outputs float above battery; SW is the undivided switched VSNS feed. EP_FLOAT remains unconnected and is protected as a physical floating pad. TLE9201 pin4 supplies the power bridge; pins5/7 are power outputs, distinct from VSO logic pin2. No package exception or transient qualification follows from this classification.',
      'nets':domains}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('netlist',type=Path);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();r=report(a.netlist);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='nets'},indent=2))
