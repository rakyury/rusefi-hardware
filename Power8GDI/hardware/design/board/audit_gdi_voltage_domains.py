"""Identify PT2001 switching-domain nets from actual connectivity, not names.

This is a conservative candidate set, not a voltage/transient simulation or an
insulation certification. It deliberately does not infer that gate/source nets
are low voltage relative to the rest of the board merely because Vgs is small.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SOURCE = 'https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf'
# MC33PT2001 short datasheet Rev10.1, Table2, pp6-7. No MC33816
# electrical limits are substituted for the selected PT2001 part.
PINS = {str(39-i): f'D_LS{i}' for i in range(1,7)}
PINS['48'] = 'VBOOST'
for i in range(1,6):
    for offset, role in [(0,'S_HS'), (1,'G_HS'), (2,'B_HS')]:
        PINS[str(66-3*i-offset)] = f'{role}{i}'


def discover(netlist):
    """Return exact net names and original XML evidence; reject wrong pin maps."""
    doc = ET.parse(netlist)
    parts = {c.get('ref'): c for c in doc.findall('components/comp')}
    nets = {n.get('name'): [dict(q.attrib) for q in n.findall('node')]
            for n in doc.findall('nets/net')}
    pad_net = {(q['ref'],q['pin']): name for name, nodes in nets.items() for q in nodes}
    refs = defaultdict(set)
    for (ref,pin),name in pad_net.items():
        refs[ref].add(name)
    reasons = defaultdict(set)
    resistor_seeds = set()
    boost_seeds = set()
    for ref in ('U201','U301'):
        if parts[ref].findtext('value') != 'MC33PT2001AE':
            raise ValueError(f'{ref}: selected device changed; re-review voltage map')
        for pin, function in PINS.items():
            name = pad_net[(ref,pin)]
            node = next(q for q in nets[name] if q['ref']==ref and q['pin']==pin)
            if node.get('pinfunction') != function:
                raise ValueError(f'{ref}.{pin}: expected {function}, got {node}')
            reasons[name].add(f'{ref}.{pin} {function}')
            if function.startswith(('G_HS','D_LS')):
                resistor_seeds.add(name)
            if function == 'VBOOST':
                boost_seeds.add(name)
    # Only one series-resistor hop: do not spread through arbitrary resistor
    # networks into ground/logic. Existing gate resistors and drain-monitor
    # branches preserve the corresponding common-mode switching domain.
    for name in sorted(resistor_seeds):
        for q in nets[name]:
            ref = q['ref']
            if ref.startswith('R') and len(refs[ref]) == 2:
                for other in refs[ref]-{name}:
                    if other == 'GND' or other.startswith(('+3V3','+5V')):
                        raise ValueError(f'{ref}: unexpected switching-domain tie to {other}')
                    reasons[other].add(f'Via series {ref} from {name}')
    for name in sorted(boost_seeds):
        for q in nets[name]:
            if q['ref'].startswith('D') and q.get('pinfunction') == 'K':
                ref = q['ref']
                for other in refs[ref]-{name}:
                    if any(n['ref']==ref and n.get('pinfunction')=='A' for n in nets[other]):
                        reasons[other].add(f'Anode of {ref}; cathode on {name}')
    return {name: {'evidence':sorted(why), 'nodes':nets[name]}
            for name,why in sorted(reasons.items())}


def audit(netlist, project):
    domains = discover(netlist)
    pro = json.loads(project.read_text())
    settings = pro['net_settings']
    classes = {c['name']:c for c in settings['classes']}
    rules_path = project.with_suffix('.kicad_dru')
    rules = rules_path.read_text()
    # The project's generated explicit rules use only ORed A.NetName equality
    # expressions. Report these separately, without emulating the DRC engine.
    explicit = defaultdict(list)
    for line in rules.splitlines():
        minimum = re.search(r'\(constraint clearance \(min ([\d.]+)mm\)',line)
        if not minimum:
            continue
        for name in re.findall(r"A\.NetName == '([^']+)'",line):
            explicit[name].append(float(minimum.group(1)))
    gaps = []
    for name, entry in domains.items():
        matched = [c['netclass'] for c in settings.get('netclass_patterns',[])
                   if fnmatch.fnmatchcase(name,c['pattern'])]
        direct = settings.get('netclass_assignments',{}).get(name)
        if direct:
            matched += [direct] if isinstance(direct,str) else list(direct)
        entry['matching_project_classes'] = sorted(set(matched)) or ['Default']
        entry['matching_class_clearances_mm'] = {
            c:classes[c]['clearance'] for c in entry['matching_project_classes']}
        entry['explicit_clearance_minima_mm'] = explicit[name]
        if not any(v >= .6 for v in explicit[name]):
            gaps.append(name)
    return {
        'scope':'Conservative PT switching-domain coverage audit; not complete voltage or DRC qualification',
        'datasheet':SOURCE, 'datasheet_revision':'10.1, Table2 pp6-7',
        'netlist_sha256':hashlib.sha256(netlist.read_bytes()).hexdigest(),
        'project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),
        'rules_sha256':hashlib.sha256(rules_path.read_bytes()).hexdigest(),
        'switching_domain_net_count':len(domains),
        'nets_without_explicit_existing_0p6mm_target':gaps,
        'interpretation':'0.6mm is the existing project engineering target, not a requirement derived from this short datasheet. Package escapes, within-domain differential voltage, fabrication and transients need separate review. No rules changed or waived.',
        'nets':domains,
    }


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('netlist',type=Path)
    ap.add_argument('project',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    report=audit(args.netlist,args.project)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='nets'},indent=2))
