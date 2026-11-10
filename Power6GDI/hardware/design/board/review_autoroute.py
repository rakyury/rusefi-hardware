"""Measure the machine copper of an autorouted candidate, block by block. Read-only.

  python3 review_autoroute.py <placement.kicad_pcb> <autorouted.kicad_pcb> <out dir> [--layout-profile P]

Router items are the tracks and vias of the autorouted board whose geometry is
not in the placement candidate. Every number here comes from the board: which
functional block each net belongs to, which board area and layer the copper
sits in, widths against the project netclasses, the project's own clearance
rule (voltage_domains) applied to every router item - the KiCad DRC report is
capped at 500 per category, so it cannot show whether the router added
violations - sensitive nets running within 1 mm of switching or high-voltage
copper, differential pairs the router could not keep together, GND islands left
after the run, and the remaining connectivity gap bucketed by block. Verdicts
are written by a person in the review document; this file only measures.
"""
from collections import Counter,defaultdict
from pathlib import Path
import fnmatch
import json
import math
import re
import sys
import pcbnew as p
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import voltage_domains
import layout_profile
import ground_stitch
from route_wbo_local import Copper,bounds,xy,track_fingerprint

LAYERS={p.F_Cu:'F.Cu',p.In1_Cu:'In1.Cu',p.In2_Cu:'In2.Cu',p.B_Cu:'B.Cu'}
DONOR_REFS={'A':re.compile(r'[A-Z]+2\d\d'),'B':re.compile(r'[A-Z]+3\d\d')}  # GDI-4ch donor stage references
MIN_FAB_WIDTH_MM=.15
BLOCK_RULES=[  # first match wins; nets in voltage_domains' GDI set are gdi_hv before these run
    ('gnd',r'GND|HARNESS_SENSOR_GND_.*'),
    ('ignition_hv',r'HARNESS_IGN[1-8]'),
    ('battery',r'VBAT.*|PT[AB]_\+Batt_filtered'),
    ('logic_supply',r'\+3V3|\+3V3_A|\+5V_CORE|\+5V_GDI_[AB]|SENSOR_5V_[AB]|WBO1_3V3|SD_3V3|PT[AB]_VCC.*|LP33_(?!SW).*|LP5_(?!SW|BOOT).*|PGOOD_.*|KNOCK_VREF|WBO1_REF3V3|SAFETY_5V_SENSE|USB_HOST_VBUS|LIN\d_VSUP'),
    ('switching_supply',r'LP5_SW|LP5_BOOT|LP33_SW'),
    ('comms',r'CAN\d_.*|USB_.*|LIN\d_.*|WBO1_CAN_.*'),
    ('analog_sensor',r'ADC_.*|.*_DIV|.*_BUFFER|KNOCK.*|CRANK|HARNESS_KNOCK.*|VR_CRANK.*|HARNESS_CRANK_VR.*|SENSOR_[AB]_IN|HARNESS_(FRP|PPS|TPS|MAP|CLT|IAT|OIL|EXH|BARO|LPFP|EWG_POS).*|WBO1_.*(sense|dac|Vm|REF_SET).*'),
    ('digital_sensor',r'HALL\d.*|CAM\d.*|SENT\d.*|FLEX_.*|HARNESS_(HALL|CAM|SENT|FLEX).*'),
    ('ignition_driver',r'IGN\d.*|IGN_.*'),
    ('gdi_control',r'PT[AB]_.*|GDI_.*|Net-\(U[23]01-.*|Net-\(Q[23]\d\d-.*|Net-\(C[23]\d\d-.*|Net-\(D[23]\d\d-.*'),
    ('low_side_outputs',r'DI\d|PI\d.*|HPFP\d|LS\d_.*|LS_.*|VVT.*|AUX_PWM.*|HARNESS_(LS|AUX|VVT|PI).*'),
    ('motor',r'DBW_.*|EWG_.*|MOTOR.*'),
    ('wbo',r'WBO1_.*|HARNESS_WBO1_.*'),
    ('mcu_core',r'MCU_.*|NRST|BOOT0|SW(CLK|O|DIO)|SD_.*|WD_CWD|HW_.*|SAFETY_.*|AUX_SPI.*'),
]
SENSITIVE=re.compile(r'ADC_.*|.*_DIV|.*_BUFFER|KNOCK.*|VR_CRANK.*|HARNESS_CRANK_VR.*|SENSOR_[AB]_IN|WBO1_.*(sense|dac|Vm|REF_SET).*|NRST|BOOT0|HW_KILL_N|HW_ACTUATOR_ENABLE|SAFETY_FAULT_N|IGN_SAFE_EN|CAM\d.*|HALL\d.*|SENT\d.*|FLEX_.*')
AGGRESSOR_EXTRA=re.compile(r'VBAT.*|LP5_SW|LP5_BOOT|LP33_SW|GDI_[AB]_(SW|MID|CAP)|MOTOR\d\d_(SW|MID|VS|CAP)|DBW_MOTOR_[AB]|EWG_MOTOR_[AB]|DI\d|HPFP\d|IGN\d_(GATE|DRIVE)|HARNESS_IGN\d')
PAIRS=[('CAN1_H','CAN1_L'),('CAN2_H','CAN2_L'),('USB_DP','USB_DM'),('HARNESS_CRANK_VR_P','HARNESS_CRANK_VR_N'),('VR_CRANK_P_FILT','VR_CRANK_N_FILT')]
COUPLING_MM=1.0
AUDIT_MARGIN_MM=.001
MATCH_QUANTUM_NM=10000  # 10 um: SES import re-creates every wire; coordinates come back rounded


def loose_key(t):
    """Geometry key tolerant to SES rounding: net, layer, sorted endpoints at 10 um, width."""
    q=MATCH_QUANTUM_NM;via=t.Type()==p.PCB_VIA_T
    if via:pos=t.GetPosition();pts=((round(pos.x/q),round(pos.y/q)),)
    else:s,e=t.GetStart(),t.GetEnd();pts=tuple(sorted(((round(s.x/q),round(s.y/q)),(round(e.x/q),round(e.y/q)))))
    return (t.GetNetname(),'via' if via else t.GetLayer(),pts,t.GetWidth(p.F_Cu) if via else t.GetWidth())


def split_router_items(base,board,hv_nets):
    """Router items = autorouted copper with no counterpart in the placement candidate (exact, then 10 um).
    Also reports placement copper that came back altered or missing - the SES import re-creates every
    unlocked wire, so reviewed copper is only safe if it matches again."""
    base_exact={track_fingerprint(t) for t in base.GetTracks()};base_loose=Counter(loose_key(t) for t in base.GetTracks())
    auto_exact={track_fingerprint(t) for t in board.GetTracks()};auto_loose=Counter(loose_key(t) for t in board.GetTracks())
    router=[];exact=rounded=0
    for t in board.GetTracks():
        if track_fingerprint(t) in base_exact:exact+=1
        elif loose_key(t) in base_loose:rounded+=1
        else:router.append(t)
    lost=[t for t in base.GetTracks() if track_fingerprint(t) not in auto_exact and loose_key(t) not in auto_loose]
    by_block=Counter(classify(t.GetNetname(),hv_nets) for t in lost);by_net=Counter(t.GetNetname() for t in lost)
    widths=Counter(str(round(p.ToMM(t.GetWidth(p.F_Cu) if t.Type()==p.PCB_VIA_T else t.GetWidth()),3)) for t in lost)
    return router,{'placement_items':len(list(base.GetTracks())),'autorouted_items':len(list(board.GetTracks())),
                   'matched_exact':exact,'matched_within_10um':rounded,
                   'placement_items_altered_or_removed':len(lost),'altered_by_block':dict(by_block.most_common()),
                   'altered_by_net':by_net.most_common(30),'altered_widths_mm':dict(widths.most_common()),
                   'altered_examples':[{'net':t.GetNetname(),'layer':LAYERS.get(t.GetLayer(),'via'),'at_mm':[round(v,2) for v in midpoint(t)],
                                        'width_mm':round(p.ToMM(t.GetWidth(p.F_Cu) if t.Type()==p.PCB_VIA_T else t.GetWidth()),3)} for t in lost[:60]]}
PAIR_GAP_MM=.5


def classify(name,hv_nets):
    if name in hv_nets:return 'gdi_hv'
    for block,pattern in BLOCK_RULES:
        if re.fullmatch(pattern,name):return block
    return 'other'


def donor_rects(board):
    """Bounding box of each donor stage's footprints (courtyards excluded)."""
    out={}
    for stage,pattern in DONOR_REFS.items():
        boxes=[bounds(f) for f in board.GetFootprints() if pattern.fullmatch(f.GetReference())]
        if not boxes:raise ValueError('No donor footprints for stage '+stage)
        out['stage_'+stage]=tuple(round(v,1) for v in (min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)))
    return out


def areas(stage_rects):
    """Stage areas first (donor copper), then the profile regions not covered by them."""
    pr=layout_profile.profile();out=dict(stage_rects)
    for key,name in (('ignition_permission','ignition_row'),('mcu','mcu'),('sensor_trackers','right_column')):
        out[name]=tuple(pr['regions'][key]['rect_mm'])
    w,h=pr['outline_mm'];ymax=max(a[3] for a in out.values());out['connector_strip']=(0,ymax,w,h)
    return out


def area_of(point,table):
    for name,(x0,y0,x1,y1) in table.items():
        if x0<=point[0]<=x1 and y0<=point[1]<=y1:return name
    return 'elsewhere'


def midpoint(t):
    if t.Type()==p.PCB_VIA_T:return xy(t)
    a,b=t.GetStart(),t.GetEnd();return (p.ToMM(a.x+b.x)/2,p.ToMM(a.y+b.y)/2)


def netclass_widths(pro_path):
    """Track width per net from the project: explicit assignments, then wildcard patterns."""
    pro=json.loads(Path(pro_path).read_text())['net_settings']
    classes={c['name']:c['track_width'] for c in pro['classes']}
    assigned={net:classes[v[0]] for net,v in pro.get('netclass_assignments',{}).items()}
    patterns=[(re.compile(fnmatch.translate(q['pattern'])),classes[q['netclass']]) for q in pro.get('netclass_patterns',[])]
    class Widths(dict):
        def get(self,net,default=None):
            if net in self:return self[net]
            for rx,width in patterns:
                if rx.match(net):return width
            return default
    return classes['Default'],Widths(assigned)


def copper_index(board,layers=tuple(LAYERS)):
    """Every copper item of the board, zones by their actual fill, binned per layer."""
    copper=Copper()
    for item in [q for f in board.GetFootprints() for q in f.Pads()]+list(board.GetTracks()):
        for layer in layers:copper.add(item,layer)
    for z in board.Zones():
        if z.GetIsRuleArea():continue
        for layer in layers:
            if not z.IsOnLayer(layer):continue
            poly=z.GetFilledPolysList(layer)
            if not poly.OutlineCount():continue
            entry=(z,poly,z.GetNetname(),bounds(z,2.6));copper.items.append(entry)
            for cell in copper.cells(entry[3]):copper.bins[layer,cell].append(entry)
    return copper


def nearby(copper,shape,b,layer,net,gap,select):
    """Other-net items within gap of shape on layer, filtered by select(netname)."""
    seen=set();hits=[]
    for cell in copper.cells(b):
        for item,other,othernet,ob in copper.bins[layer,cell]:
            if id(item) in seen or othernet==net or not select(othernet):continue
            seen.add(id(item))
            if other.Collide(shape,p.FromMM(gap)):hits.append(othernet)
    return hits


def shape_of(t,layer):
    return t.GetEffectiveShape(layer) if t.Type()==p.PCB_VIA_T else t.GetEffectiveShape()


def item_layers(t):
    return [l for l in LAYERS if t.IsOnLayer(l)] if t.Type()==p.PCB_VIA_T else [t.GetLayer()]


def clusters(board,net_items,zone_polys):
    """Connected groups of a net's pads/tracks/vias; same-net zone fills join groups."""
    c=board.GetConnectivity();seen=set();groups=[]
    def zone_keys(item):
        keys=set()
        for layer in item_layers(item) if item.Type()!=p.PCB_PAD_T else [l for l in LAYERS if item.IsOnLayer(l)]:
            for key,(zl,poly) in zone_polys.items():
                if zl==layer and poly.Collide(item.GetEffectiveShape(layer),0):keys.add(key)
        return keys
    for start in net_items:
        if start.m_Uuid.AsString() in seen:continue
        queue=[start];members=0;zones=set()
        while queue:
            item=queue.pop();key=item.m_Uuid.AsString()
            if key in seen:continue
            seen.add(key);members+=1;zones|=zone_keys(item)
            queue.extend(list(c.GetConnectedPads(item))+list(c.GetConnectedTracks(item)))
        groups.append(zones)
    # Merge groups that touch the same zone fill.
    merged=[]
    for zones in groups:
        hit=[g for g in merged if g&zones]
        for g in hit:merged.remove(g);zones=zones|g
        merged.append(zones if zones else frozenset({object()}))
    return len(merged)


def remaining_gap(board,hv_nets):
    items=defaultdict(list)
    for f in board.GetFootprints():
        for q in f.Pads():
            if q.GetNetname():items[q.GetNetname()].append(q)
    for t in board.GetTracks():
        if t.GetNetname():items[t.GetNetname()].append(t)
    zone_polys=defaultdict(dict)
    for i,z in enumerate(board.Zones()):
        if z.GetIsRuleArea():continue
        for layer in LAYERS:
            if z.IsOnLayer(layer) and z.GetFilledPolysList(layer).OutlineCount():zone_polys[z.GetNetname()][(i,layer)]=(layer,z.GetFilledPolysList(layer))
    per_net={}
    for net,group in items.items():
        n=clusters(board,group,zone_polys.get(net,{}))
        if n>1:per_net[net]=n-1
    by_block=Counter()
    for net,n in per_net.items():by_block[classify(net,hv_nets)]+=n
    return {'total':sum(per_net.values()),'by_block':dict(by_block.most_common()),
            'worst_nets':sorted(per_net.items(),key=lambda kv:-kv[1])[:25],
            'unclassified_nets':sorted(n for n in per_net if classify(n,hv_nets)=='other')}


def pair_metrics(router,board):
    out={}
    tracks=defaultdict(list)
    for t in router:
        if t.Type()!=p.PCB_VIA_T:tracks[t.GetNetname()].append(t)
    for a,b in PAIRS:
        ta,tb=tracks.get(a,[]),tracks.get(b,[])
        if not ta and not tb:continue
        la=sum(p.ToMM(t.GetLength()) for t in ta);lb=sum(p.ToMM(t.GetLength()) for t in tb)
        shapes=[(t.GetLayer(),t.GetEffectiveShape()) for t in tb]
        samples=paired=0
        for t in ta:
            n=max(1,int(p.ToMM(t.GetLength())/.5))
            for i in range(n+1):
                s,e=t.GetStart(),t.GetEnd();pt=p.VECTOR2I(int(s.x+(e.x-s.x)*i/n),int(s.y+(e.y-s.y)*i/n))
                samples+=1
                if any(l==t.GetLayer() and sh.Collide(pt,p.FromMM(PAIR_GAP_MM+.1)) for l,sh in shapes):paired+=1
        vias={net:sum(1 for t in router if t.Type()==p.PCB_VIA_T and t.GetNetname()==net) for net in (a,b)}
        out[f'{a}/{b}']={'router_length_mm':[round(la,1),round(lb,1)],'mismatch_mm':round(abs(la-lb),1),'router_vias':vias,
                         'fraction_within_%gmm_of_partner'%PAIR_GAP_MM:round(paired/samples,2) if samples else None}
    return out


def review(placement,autorouted,out,profile):
    layout_profile.configure(profile)
    voltage_domains.configure(HERE.parent/'core.net');hv=voltage_domains.gdi_high_voltage_nets()
    aggressor=lambda n:n in hv or bool(AGGRESSOR_EXTRA.fullmatch(n))
    base=p.LoadBoard(str(placement));board=p.LoadBoard(str(autorouted));board.BuildConnectivity()
    router,preexisting=split_router_items(base,board,hv)
    default_w,assigned=netclass_widths(Path(autorouted).with_suffix('.kicad_pro'))
    table=areas(donor_rects(board));copper=copper_index(board)
    blocks=defaultdict(lambda:{'nets':set(),'tracks':0,'vias':0,'length_mm':0.0,'length_by_layer_mm':Counter(),'items_by_area':Counter(),
                               'in1_items':0,'width_below_class':0,'width_below_fab_min':0,'min_width_mm':None,'width_histogram_mm':Counter(),'clearance_violations':0,'coupled_segments':0,'coupled_length_mm':0.0,'coupled_with':Counter()})
    violations=[];coupled=[];in1=[]
    for t in router:
        net=t.GetNetname();block=classify(net,hv);b=blocks[block];b['nets'].add(net)
        area=area_of(midpoint(t),table);b['items_by_area'][area]+=1
        is_via=t.Type()==p.PCB_VIA_T
        if is_via:b['vias']+=1
        else:
            b['tracks']+=1;length=p.ToMM(t.GetLength());b['length_mm']+=length;b['length_by_layer_mm'][LAYERS.get(t.GetLayer(),str(t.GetLayer()))]+=length
            w=p.ToMM(t.GetWidth());b['min_width_mm']=w if b['min_width_mm'] is None else min(b['min_width_mm'],w);b['width_histogram_mm'][str(round(w,3))]+=1
            if w+1e-6<assigned.get(net,default_w):b['width_below_class']+=1
            if w+1e-6<MIN_FAB_WIDTH_MM:b['width_below_fab_min']+=1
            if t.GetLayer()==p.In1_Cu:b['in1_items']+=1;in1.append({'net':net,'block':block,'length_mm':round(length,2),'at_mm':[round(v,2) for v in midpoint(t)]})
        for layer in item_layers(t):
            shape=shape_of(t,layer);bb=bounds(t,.01)
            if not copper.clear(shape,bb,layer,net,margin=-AUDIT_MARGIN_MM):
                b['clearance_violations']+=1
                if len(violations)<200:violations.append({'net':net,'block':block,'layer':LAYERS[layer],'via':is_via,'at_mm':[round(v,2) for v in midpoint(t)]})
            if not is_via and SENSITIVE.fullmatch(net):
                hits=nearby(copper,shape,bb,layer,net,COUPLING_MM,aggressor)
                if hits:
                    b['coupled_segments']+=1;b['coupled_length_mm']+=p.ToMM(t.GetLength())
                    for h in set(hits):b['coupled_with'][h]+=1
                    if len(coupled)<200:coupled.append({'net':net,'layer':LAYERS[layer],'length_mm':round(p.ToMM(t.GetLength()),2),'near':sorted(set(hits)),'at_mm':[round(v,2) for v in midpoint(t)]})
    for b in blocks.values():
        b['nets']=sorted(b['nets']);b['net_count']=len(b['nets']);b['length_mm']=round(b['length_mm'],1);b['coupled_length_mm']=round(b['coupled_length_mm'],1)
        b['length_by_layer_mm']={k:round(v,1) for k,v in b['length_by_layer_mm'].most_common()}
        b['items_by_area']=dict(b['items_by_area'].most_common());b['coupled_with']=dict(b['coupled_with'].most_common(8));b['width_histogram_mm']=dict(b['width_histogram_mm'].most_common())
    plane,islands=ground_stitch.islands(board)
    before=json.loads((Path(placement).parent/'ground_stitch.json').read_text())
    gnd_router=[t for t in router if t.GetNetname()=='GND']
    report={'qualification':'MEASUREMENT OF MACHINE COPPER; verdicts live in the review document',
            'placement':str(placement),'autorouted':str(autorouted),'preexisting_copper':preexisting,'router_items':len(router),
            'router_tracks':sum(t.Type()!=p.PCB_VIA_T for t in router),'router_vias':sum(t.Type()==p.PCB_VIA_T for t in router),
            'areas_mm':table,'areas_note':'stage_A/stage_B are bounding boxes of the donor footprints (refs 2xx / 3xx); other areas come from the layout profile regions','netclass_default_width_mm':default_w,'fab_min_width_mm':MIN_FAB_WIDTH_MM,
            'clearance_rule':'voltage_domains.clearance_mm per net pair (HARNESS_IGN 2.5 / GDI HV 0.6 / battery 0.3 / default 0.2) minus %g mm, applied to every router item against all copper incl. zone fills; copper at exactly the rule distance passes'%AUDIT_MARGIN_MM,
            'router_clearance_violations':sum(b['clearance_violations'] for b in blocks.values()),'clearance_examples':violations,
            'coupling_rule':'sensitive-net router segment within %g mm of GDI HV / ignition / battery / switching copper on the same layer'%COUPLING_MM,
            'coupling_examples':coupled,'in1_router_tracks':in1,
            'gnd':{'router_tracks':sum(t.Type()!=p.PCB_VIA_T for t in gnd_router),'router_vias':sum(t.Type()==p.PCB_VIA_T for t in gnd_router),
                   'router_length_mm':round(sum(p.ToMM(t.GetLength()) for t in gnd_router if t.Type()!=p.PCB_VIA_T),1),
                   'islands_before_router':len(before['unstitched']),'islands_after_router':len(islands),'plane_pads_after':len(plane)},
            'pairs':pair_metrics(router,board),
            'unconnected_kicad':board.GetConnectivity().GetUnconnectedCount(False),
            'remaining_gap':remaining_gap(board,hv),
            'blocks':dict(sorted(blocks.items(),key=lambda kv:-kv[1]['tracks']))}
    out.mkdir(parents=True,exist_ok=True)
    (out/'autoroute_review.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
    for name,b in report['blocks'].items():
        print(f"{name:18s} nets {b['net_count']:3d} tracks {b['tracks']:5d} vias {b['vias']:4d} len {b['length_mm']:8.1f} in1 {b['in1_items']:3d} thin {b['width_below_class']:4d}/{b['width_below_fab_min']:4d} clr {b['clearance_violations']:4d} coupled {b['coupled_segments']:4d} areas {b['items_by_area']}")
    print('preexisting',{k:v for k,v in preexisting.items() if not k.startswith('altered_')},'altered by block',preexisting['altered_by_block'])
    print('router clearance violations',report['router_clearance_violations'],'in1 tracks',len(in1))
    print('gnd',report['gnd']);print('pairs',json.dumps(report['pairs'],indent=1))
    print('unconnected kicad',report['unconnected_kicad'],'clusters',report['remaining_gap']['total'],report['remaining_gap']['by_block'])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('placement',type=Path);parser.add_argument('autorouted',type=Path);parser.add_argument('out',type=Path)
    parser.add_argument('--layout-profile',type=Path,default=HERE/'layout_profiles/190x206_donor.json')
    a=parser.parse_args()
    review(a.placement.resolve(),a.autorouted.resolve(),a.out.resolve(),a.layout_profile)
