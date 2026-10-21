"""Write honest DRC/net coverage from the saved board and the full KiCad report."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import pcbnew as p


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board',type=Path);parser.add_argument('drc',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();board=p.LoadBoard(str(args.board));report=json.loads(args.drc.read_text())
    objects={};pins=defaultdict(set)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            objects[pad.m_Uuid.AsString()]=pad.GetNetname()
            if pad.GetNumber() and pad.GetNetname():pins[pad.GetNetname()].add(f'{fp.GetReference()}.{pad.GetNumber()}')
    for track in board.GetTracks():objects[track.m_Uuid.AsString()]=track.GetNetname()
    unrouted=Counter()
    for violation in report['unconnected_items']:
        for net in {objects.get(item['uuid']) for item in violation['items']} - {None,''}:unrouted[net]+=1
    violations=Counter(x['type'] for x in report['violations'])
    multiple={n for n,ps in pins.items() if len(ps)>1}
    result={'manufacturing_gate':'FAIL','violations':dict(violations),'total_violations':len(report['violations']),
            'unconnected_items':len(report['unconnected_items']),'multi_terminal_nets':len(multiple),
            'multi_terminal_nets_with_missing_connections':len(multiple & unrouted.keys()),
            'multi_terminal_nets_without_reported_missing_connection':len(multiple-unrouted.keys()),
            'singleton_harness_nets':sorted(n for n,ps in pins.items() if len(ps)==1 and n.startswith('HARNESS_')),
            'nets':{n:{'pads':sorted(ps),'missing_connections':unrouted[n]} for n,ps in sorted(pins.items())},
            'interpretation':'No missing connection in DRC does not prove correctness, safety, electrical ratings or absence of shorts. Singleton requested interfaces remain unimplemented.'}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('nets','singleton_harness_nets')},indent=2))
