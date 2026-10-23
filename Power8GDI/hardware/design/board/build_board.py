"""Build the review PCB from authoritative XML netlists with KiCad 9 pcbnew.

Run under the pinned official KiCad image. Missing inputs and pin/copper net
conflicts fail; incomplete routes remain visible to KiCad's DRC/ratsnest.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pcbnew as p
from build_connector import make_footprint, vec
from copper_transfer import audited_copper
from net_contract import read_netlists, compare_pad_assignments
from board_cleanup import arrange_references, remove_dangling, Spatial

HERE = Path(__file__).resolve().parent
_FOOTPRINT_CACHE = {}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mm(point): return [p.ToMM(point.x), p.ToMM(point.y)]
def pad_of(fp, number): return next(q for q in fp.Pads() if q.GetNumber() == str(number))


def apply_attributes(fp,component):
    fp.SetDNP(component['dnp'])
    fp.SetExcludedFromBOM(component['exclude_from_bom'])
    # An on-board exclusion is not permission to create a physical pad anyway.
    if component['exclude_from_board']:
        raise ValueError(f"Off-board component unexpectedly included: {fp.GetReference()}")


def connector_contract(pinout, output):
    aliases = {row['pinout_net']: row['board_net'] for row in csv.DictReader((HERE/'connector_aliases.csv').open())}
    root = ET.Element('export',version='E'); comps=ET.SubElement(root,'components'); nets={}
    for connector in 'ABCD':
        comp=ET.SubElement(comps,'comp',ref=f'J60{"ABCD".index(connector)+1}')
        ET.SubElement(comp,'value').text='6437288-1 (key1 candidate)'
        ET.SubElement(comp,'footprint').text='Power8GDI_Board:TE_6437288-1_34way'
    rows=list(csv.DictReader(Path(pinout).open()))
    if len(rows)!=136 or len({(r['connector'],r['position']) for r in rows})!=136:
        raise ValueError('Connector pinout must contain exactly4x34 unique positions')
    for row in rows:
        name=aliases.get(row['net'],'HARNESS_'+row['net'])
        nets.setdefault(name,[]).append((f'J60{"ABCD".index(row["connector"])+1}',row['position']))
    outnets=ET.SubElement(root,'nets')
    for code,(name,pins) in enumerate(sorted(nets.items()),1):
        net=ET.SubElement(outnets,'net',code=str(code),name=name)
        for ref,pin in pins: ET.SubElement(net,'node',ref=ref,pin=pin)
    ET.indent(root)
    ET.ElementTree(root).write(output,encoding='utf-8',xml_declaration=True)
    return rows,aliases


def load_footprint(identifier, design):
    cache_key=(str(design.resolve()),identifier)
    if cache_key in _FOOTPRINT_CACHE:return _FOOTPRINT_CACHE[cache_key].Duplicate()
    library,name=identifier.split(':',1)
    libraries={'Power8GDI_Board':HERE/'Power8GDI_Board.pretty',
               'Power8GDI_Core':design/'Power8GDI_Core.pretty',
               'Power8GDI_Interfaces':design/'interfaces/Power8GDI_Interfaces.pretty',
               'Power8GDI_Motor4':design/'motor4/Power8GDI_Motor4.pretty',
               'Power8GDI_GDIProtection':design/'gdi/Power8GDI_GDIProtection.pretty',
               'Power8GDI_GDI':design/'gdi/Power8GDI_GDI.pretty'}
    path=libraries.get(library,Path('/usr/share/kicad/footprints')/(library+'.pretty'))
    footprint=p.PCB_IO_MGR.PluginFind(p.PCB_IO_MGR.KICAD_SEXP).FootprintLoad(str(path),name)
    if footprint is None: raise ValueError(f'Missing footprint {identifier} at {path}')
    footprint.SetFPID(p.LIB_ID(library,name))
    _FOOTPRINT_CACHE[cache_key]=footprint
    return footprint.Duplicate()


def add_track(board, net, points, width=.25, layer=p.F_Cu):
    for a,b in zip(points,points[1:]):
        if a==b: continue
        t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b))
        t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(net);board.Add(t)


def via(board,net,point):
    v=p.PCB_VIA(board);v.SetPosition(vec(*point));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3))
    v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(net);board.Add(v)


def ground_pad(board,pad,nets,direction=(0,1)):
    pos=mm(pad.GetPosition()); dest=[pos[0]+direction[0]*1.1,pos[1]+direction[1]*1.1]
    add_track(board,nets['GND'],[pos,dest],.3);via(board,nets['GND'],dest)


def move_group(items, target, angle=0, bounds_items=None):
    if angle:
        for item in items: item.Rotate(vec(0,0),p.EDA_ANGLE(angle,p.DEGREES_T))
    bbs=[f.GetBoundingBox(False,False) for f in (bounds_items or items)]
    delta=vec(target[0]-p.ToMM(min(bb.GetX() for bb in bbs)),target[1]-p.ToMM(min(bb.GetY() for bb in bbs)))
    for item in items: item.Move(delta)
    return mm(delta)


def add_plane(board,nets):
    zone=p.ZONE(board);zone.SetLayer(p.In1_Cu);zone.SetNet(nets['GND'])
    zone.SetLocalClearance(p.FromMM(.25));zone.SetThermalReliefGap(p.FromMM(.3));zone.SetThermalReliefSpokeWidth(p.FromMM(.4))
    zone.SetPadConnection(p.ZONE_CONNECTION_FULL)
    poly=zone.Outline();poly.NewOutline()
    for x,y in [(1,1),(244,1),(244,164),(1,164)]: poly.Append(p.FromMM(x),p.FromMM(y))
    board.Add(zone)


def core_placement(board, footprints, manifest, nets):
    fixed={'U101':(70,116,0),'U102':(28,103,0),'U103':(130,132,0),
           'C125':(22,103,90),'C126':(35,103,90),'C127':(124,131,90),'C128':(135,134,90),
           'J101':(12,129,0),'R104':(123,136,0),'R105':(123,140,0),'R106':(138,131,90),
           'C114':(91,137,0),'C115':(91,127,0),'C116':(71,96,90),
           'C117':(49,126,0),'C118':(46,126,90),'R101':(49,123,0),
           'C119':(79,95,90),'C120':(83,95,0),'C121':(91,110,0),'C122':(95,110,90),
           'C123':(53,107,0),'C124':(47,110,0),'R102':(43,110,0),'R103':(60,97,90),
           'Y101':(49,133,0),'C129':(52,138,0),
           'U104':(109,133,0),'R107':(102,130,0),'R108':(102,134,0),'R109':(102,138,0),
           'R110':(109,139,0),'R111':(112,125,0),'C130':(116,130,0),'C131':(116,134,0),'C132':(116,138,0),'D101':(120,142,0)}
    for ref,(x,y,a) in fixed.items():
        if ref in footprints:
            footprints[ref].SetPosition(vec(x,y));footprints[ref].SetOrientationDegrees(a)
    decoupled=set()
    for entry in manifest['decoupling_placement']:
        ref=entry['reference']; cap=footprints[ref]; mcu=footprints['U101']; pad=pad_of(mcu,entry['mcu_pad'])
        x,y=mm(pad.GetPosition()); cx,cy=mm(mcu.GetPosition())
        if abs(x-cx)>abs(y-cy):
            direction=1 if x>cx else -1; location=(x+direction*3,y)
            cap.SetOrientationDegrees(0 if direction>0 else 180)
            outward=(direction,0)
        else:
            direction=1 if y>cy else -1; location=(x,y+direction*3)
            cap.SetOrientationDegrees(270 if direction>0 else 90)
            outward=(0,direction)
        cap.SetPosition(vec(*location));decoupled.add(ref)
        add_track(board,nets[pad.GetNetname()],[mm(pad.GetPosition()),mm(pad_of(cap,'1').GetPosition())],.25)
        ground_pad(board,pad_of(cap,'2'),nets,outward)
    io=set()
    for channel in range(4):
        x,y=25+channel*30+(3.5 if channel in (1,2) else 0),118
        group={f'U{110+channel}':(x,y,0),f'C{140+2*channel}':(x,y-6,0),f'C{141+2*channel}':(x,y+6,0)}
        for side in range(2):
            index=2*channel+side
            group[f'R{120+index}']=(x-7,y-2+side*4,0)
            group[f'R{128+index}']=(x+7,y-2+side*4,0)
            group[f'R{136+index}']=(x+12,y-2+side*4,0)
        for ref,(px,py,angle) in group.items():
            if ref not in footprints:continue
            fp=footprints[ref];fp.Flip(fp.GetPosition(),False);fp.SetPosition(vec(px,py));fp.SetOrientationDegrees(angle);io.add(ref)
    return set(fixed)|decoupled|io


def project_file(path):
    rules={'min_clearance':.2,'min_track_width':.2,'min_via_diameter':.6,'min_through_hole_diameter':.3,
           'min_hole_clearance':.25,'min_copper_edge_clearance':.5}
    classes=[]
    for name,width,clearance in [('Default',.25,.2),('Power',.6,.3),('GDI_HV',.8,.6),('Ignition_HV',1.5,2.5),('LogicSupply',.4,.2),('Logic',.25,.2)]:
        classes.append({'name':name,'priority':{'Default':2147483647,'Ignition_HV':0,'GDI_HV':1,'Power':2,'LogicSupply':3,'Logic':4}[name],
                        'clearance':clearance,'track_width':width,'via_diameter':.65,'via_drill':.3,
                        'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.2,'diff_pair_gap':.2,
                        'diff_pair_via_gap':.25,'wire_width':6,'bus_width':12,'line_style':0,'pcb_color':'rgba(0,0,0,0)',
                        'schematic_color':'rgba(0,0,0,0)','description':'Provisional engineering rule; fabrication and current/thermal approval pending'})
    doc={'meta':{'filename':path.name,'version':1},'board':{'design_settings':{
         'meta':{'filename':'board_design_settings.json','version':2},'rules':rules,'drc_exclusions':[]}},
         'net_settings':{'meta':{'version':4},'classes':classes,'netclass_assignments':{},'netclass_patterns':[{'pattern':'PT*_Vdrive*','netclass':'GDI_HV'},
                         {'pattern':'PT*_VBOOST','netclass':'GDI_HV'},{'pattern':'HARNESS_IGN*','netclass':'Ignition_HV'},
                         {'pattern':'VBAT*','netclass':'Power'},{'pattern':'+5V*','netclass':'LogicSupply'},{'pattern':'+3V3*','netclass':'LogicSupply'}]}}
    path.write_text(json.dumps(doc,indent=2)+'\n')
    # Explicit equivalent rules make these safety-relevant classes auditable
    # even in CLI consumers that fail to resolve project pattern assignments.
    high=['PT'+s+n for s in ('A','B') for n in ('_VBOOST','_Vdrive_coil','_Vdrive_shunt')]
    # Regulated 3.3/5 V rails use the ordinary 0.2 mm electrical clearance.
    # Their 0.5 mm-pitch packages have 0.25 mm intrinsic adjacent-pad gaps;
    # the previous battery-class rule imposed 0.3 mm even on those pad pairs.
    # This classification changes no battery, boost or ignition isolation rule.
    supplies=['VBAT_MAIN_FUSED','VBAT_LOGIC_PROTECTED','VBAT_GDI_A','VBAT_GDI_B','VBAT_DBW_FUSED','VBAT_EWG_FUSED']
    rules_text=['(version 1)']
    for label,names,clearance in [('Power clearance',supplies,.3),('GDI high voltage clearance',high,.6),
        ('Ignition preliminary isolation target - qualification pending',[f'HARNESS_IGN{i}' for i in range(1,9)],2.5)]:
        condition=' || '.join("A.NetName == '"+name+"'" for name in names)
        rules_text.append(f'(rule "{label}" (condition "{condition}") (constraint clearance (min {clearance}mm)))')
    path.with_suffix('.kicad_dru').write_text('\n'.join(rules_text)+'\n')


def place_candidate_domains(board, footprints, pending):
    """Pack new domains on the quiet lower backside, with real body bounds.

    This prevents the old six-column staging grid from placing components
    across existing parts and beyond the board edge. It is deliberately a
    placement candidate; electrical loop/coupling/thermal review remains open.
    """
    def bounds(fp):
        b=fp.GetBoundingBox(False,False)
        return (p.ToMM(b.GetX()),p.ToMM(b.GetY()),p.ToMM(b.GetRight()),p.ToMM(b.GetBottom()))
    def overlap(a,b):
        return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
    occupied=Spatial()
    # Through vias are copper on both sides even when their traces are on top.
    for item in board.GetTracks():
        if isinstance(item,p.PCB_VIA) or item.GetLayer()==p.B_Cu:
            box=item.GetBoundingBox()
            occupied.add((p.ToMM(box.GetX()),p.ToMM(box.GetY()),p.ToMM(box.GetRight()),p.ToMM(box.GetBottom())))
    for ref,fp in footprints.items():
        if ref in pending:continue
        if fp.GetLayer()==p.B_Cu or any(q.GetAttribute()==p.PAD_ATTRIB_PTH for q in fp.Pads()):
            occupied.add(bounds(fp))
    for ref in pending:
        fp=footprints[ref]
        if fp.GetLayer()!=p.B_Cu:fp.Flip(fp.GetPosition(),False)
    ordered=sorted(pending,key=lambda ref:(-(lambda b:(b[2]-b[0])*(b[3]-b[1]))(bounds(footprints[ref])),ref))
    for ref in ordered:
        fp=footprints[ref]; fp.SetPosition(vec(0,0)); b=bounds(fp)
        width,height=b[2]-b[0],b[3]-b[1]
        found=False
        for x0,y0,x1,y1 in [(6,94,151,143),(156,94,239,141)]:
            for yi in range(y0,y1):
                for xi in range(x0,x1):
                    candidate=(xi-.35,yi-.35,xi+width+.35,yi+height+.35)
                    if candidate[2]>x1 or candidate[3]>y1:continue
                    if occupied.collides(candidate):continue
                    fp.SetPosition(vec(xi-b[0],yi-b[1]));occupied.add(candidate);found=True;break
                if found:break
            if found:break
        if not found:raise ValueError('Diagnostic backside staging regions exhausted at '+ref+'; functional floorplan redesign required')
    return ordered


def place_output_banks(board,footprints):
    """Keep each four-output bank together on the lower right backside.

    The group is a placement candidate, not a thermal or current qualification.
    Reject a group when its actual body/pad boxes collide; don't silently fall
    back to scattering the driver's decoupling and gate resistors across board.
    """
    banks=[];allrefs=set()
    for bank in range(6):
        if f'U{1101+bank}' not in footprints:continue
        base=1100+bank*20
        layout={f'U{1101+bank}':(18,8.5),f'U{1121+bank}':(5,9)}
        sites=[(x,y) for y in (1,3.5) for x in (2,5,8,11)]
        sites += [(11,y) for y in (6,8.5,11,13.5)]
        sites += [(x,16) for x in (2,5,8,11,14)]
        for i,site in enumerate(sites,1):layout[f'R{base+i}']=site
        for i,site in enumerate([(17,16),(20,16),(23,16),(23,13.5)],1):layout[f'C{base+i}']=site
        banks.append(layout);allrefs.update(layout)
    if not banks:return set(),[]
    occupied=Spatial()
    for t in board.GetTracks():
        if isinstance(t,p.PCB_VIA) or t.GetLayer()==p.B_Cu:
            b=t.GetBoundingBox();occupied.add((p.ToMM(b.GetX())-.3,p.ToMM(b.GetY())-.3,p.ToMM(b.GetRight())+.3,p.ToMM(b.GetBottom())+.3))
    for ref,fp in footprints.items():
        if ref in allrefs:continue
        # Parts still at origin have not been placed yet.
        if mm(fp.GetPosition())==[0.,0.]:continue
        if fp.GetLayer()==p.B_Cu or any(q.GetAttribute()==p.PAD_ATTRIB_PTH for q in fp.Pads()):
            b=fp.GetBoundingBox(False,False);occupied.add((p.ToMM(b.GetX())-.3,p.ToMM(b.GetY())-.3,p.ToMM(b.GetRight())+.3,p.ToMM(b.GetBottom())+.3))
    result=[]
    for index,layout in enumerate(banks,1):
        offsets={}
        for ref,(x,y) in layout.items():
            fp=footprints[ref]
            if fp.GetLayer()!=p.B_Cu:fp.Flip(fp.GetPosition(),False)
            fp.SetOrientationDegrees(0);fp.SetPosition(vec(x,y))
            b=fp.GetBoundingBox(False,False)
            offsets[ref]=(p.ToMM(b.GetX())-.25,p.ToMM(b.GetY())-.25,p.ToMM(b.GetRight())+.25,p.ToMM(b.GetBottom())+.25)
        # Keep 0.5 mm to the logic-domain boundary and the connector pad field.
        found=None
        for oy in range(95,123):
            for ox in range(156,215):
                boxes=[(a+ox,b+oy,c+ox,d+oy) for a,b,c,d in offsets.values()]
                if any(c>239 or d>141 for a,b,c,d in boxes):continue
                if any(occupied.collides(box) for box in boxes):continue
                found=(ox,oy,boxes);break
            if found:break
        if found is None:
            raise ValueError(f'Four-channel LS bank {index} cannot fit the reserved B.Cu region x156..239/y95..141 with existing GDI copper. Keep outline/clearances; floorplan redesign required.')
        ox,oy,boxes=found
        for ref,(x,y) in layout.items():footprints[ref].SetPosition(vec(x+ox,y+oy))
        for bounds in boxes:occupied.add(bounds)
        result.append({'bank':index,'origin_mm':[ox,oy],'references':sorted(layout),
                       'qualification':'Grouped placement candidate; through-pad F.Cu/thermal review and DRC required'})
    return allrefs,result


def insert_stackup(path):
    # pcbnew's stackup descriptor is not exposed by KiCad9 SWIG. Add its
    # documented board-file section, then reload through KiCad for validation.
    layers=[('F.SilkS','Top Silk Screen',None),('F.Paste','Top Solder Paste',None),('F.Mask','Top Solder Mask',.01),
            ('F.Cu','copper',.07),('dielectric 1','prepreg',.12),('In1.Cu','copper',.035),
            ('dielectric 2','core',1.13),('In2.Cu','copper',.035),('dielectric 3','prepreg',.12),
            ('B.Cu','copper',.07),('B.Mask','Bottom Solder Mask',.01),('B.Paste','Bottom Solder Paste',None),('B.SilkS','Bottom Silk Screen',None)]
    lines=['(stackup']
    for name,kind,thick in layers:
        row=f'(layer "{name}" (type "{kind}")'
        if thick is not None:row+=f' (thickness {thick})'
        if name.startswith('dielectric'):row+=' (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02)'
        lines.append(row+')')
    lines.append('(copper_finish "ENIG") (dielectric_constraints no))')
    text=path.read_text()
    if '(stackup' in text:raise ValueError('Unexpected pre-existing stackup')
    path.write_text(text.replace('(setup','(setup\n'+'\n'.join(lines),1))


def build(args):
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    design=args.design_root.resolve()
    library=HERE/'Power8GDI_Board.pretty';library.mkdir(exist_ok=True)
    p.PCB_IO_MGR.PluginFind(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(library),make_footprint())
    rows,aliases=connector_contract(args.pinout,out/'connector_contract.xml')
    root_path=design/'core.net'
    root_refs={c.attrib['ref'] for c in ET.parse(root_path).findall('./components/comp')}
    paths=[root_path]
    # Root export is authoritative. Never resurrect obsolete power or WBO
    # sheets merely because historical XML files remain in the repository.
    connector_refs={'J601','J602','J603','J604'}
    if not connector_refs <= root_refs:
        if connector_refs & root_refs:raise ValueError('Partially integrated connector hierarchy')
        paths.append(out/'connector_contract.xml')
    components,assignments,sources=read_netlists(paths)
    print(f'Imported {len(components)} components and {len(assignments)} pins',flush=True)
    board=p.BOARD();board.GetDesignSettings().SetCopperLayerCount(4)
    board.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
    nets={}
    for name in sorted(set(assignments.values())):
        net=p.NETINFO_ITEM(board,name);board.Add(net);nets[name]=net
    for a,b in [((0,0),(245,0)),((245,0),(245,165)),((245,165),(0,165)),((0,165),(0,0))]:
        edge=p.PCB_SHAPE(board);edge.SetShape(p.SHAPE_T_SEGMENT);edge.SetStart(vec(*a));edge.SetEnd(vec(*b));edge.SetWidth(p.FromMM(.05));edge.SetLayer(p.Edge_Cuts);board.Add(edge)
    footprints={};source=p.LoadBoard(str(args.source_board));oldfps={f.GetReference():f for f in source.GetFootprints()}
    mapping=json.loads((design/'gdi/reference_mapping.json').read_text())
    audit={}; imported=set()
    for stage,target,angle in [('A',(5,5),0),('B',(157,2),90)]:
        print(f'Auditing stage {stage} copper',flush=True)
        refmap=mapping[stage]['reference_map']
        netmap,tracks,report=audited_copper(source,refmap,assignments)
        print(f'Stage {stage}: {len(tracks)} audited copper items',flush=True)
        group=[];group_fps=[]
        for oldref,newref in refmap.items():
            fp=oldfps[oldref].Duplicate();fp.SetReference(newref);fp.SetValue(components[newref]['value'])
            apply_attributes(fp,components[newref])
            lib,name=components[newref]['footprint'].split(':',1);fp.SetFPID(p.LIB_ID(lib,name))
            # Remove source-specific absolute model paths; exact models are a separate verified input.
            fp.Models().clear()
            board.Add(fp);footprints[newref]=fp;imported.add(newref)
            for pad in fp.Pads():
                pad.SetNet(nets[assignments[(newref,pad.GetNumber())]]) if (newref,pad.GetNumber()) in assignments else pad.SetNetCode(0)
            group.append(fp);group_fps.append(fp)
        for item in tracks:
            # These reference supply buses wrap outside the rotated footprint
            # region and cross the provisional board edge. They need new routing
            # to the new local regulator; do not pretend the old route fits.
            if stage=='B' and netmap[item.GetNetname()] in ('+3V3','+5V_GDI_B'):continue
            cloned=item.Duplicate();board.Add(cloned);cloned.SetNet(nets[netmap[item.GetNetname()]]);group.append(cloned)
        zones=0
        for z in source.Zones():
            if z.GetNetname() not in netmap or netmap[z.GetNetname()]=='GND' or z.GetIsRuleArea():continue
            cloned=z.Duplicate();board.Add(cloned);cloned.SetNet(nets[netmap[z.GetNetname()]]);cloned.UnFill();group.append(cloned);zones+=1
        delta=move_group(group,target,angle,group_fps)
        report.update({'translation_mm':delta,'rotation_degrees':angle,'zones_copied':zones,'reference_pad_net_map':netmap,
                       'supply_routing_omitted':sum(stage=='B' and netmap[t.GetNetname()] in ('+3V3','+5V_GDI_B') for t in tracks)})
        audit[stage]=report
    rest=[ref for ref in components if ref not in imported]
    print(f'Loading {len(rest)} remaining footprints',flush=True)
    for ref in rest:
        comp=components[ref];fp=load_footprint(comp['footprint'],design);fp.SetReference(ref);fp.SetValue(comp['value']);board.Add(fp)
        apply_attributes(fp,comp)
        fp.Models().clear();footprints[ref]=fp
        for pad in fp.Pads():
            key=(ref,pad.GetNumber());pad.SetNet(nets[assignments[key]]) if key in assignments else pad.SetNetCode(0)
    manifest=json.loads((design/'core_manifest.json').read_text())
    print('Placing core and power input',flush=True)
    placed=core_placement(board,footprints,manifest,nets)|imported if not args.functional_layout else set(imported)
    fixed={'J601':(37,161.5,0),'J602':(85,161.5,0),'J603':(133,161.5,0),'J604':(208,161.5,0),
           'R299':(48,90,0),'R399':(154,120,90),
           'U501':(112,103,0),'D501':(98,98,0),'D502':(98,105,90),
           'C501':(106,103,0),'C502':(106,99,0),'C503':(98,116,0),'C504':(117,101,90),
           'L501':(126,103,0),'C505':(139,101,90),'C506':(143,101,90),
           'R501':(105,108,0),'R502':(108,111,0),'R503':(109,115,0),
           'R504':(119,113,0),'R505':(115,113,0),'R506':(124,115,0),'R507':(129,115,0),
           'C507':(119,117,0),'C508':(123,120,0),
           'U249':(25,117,0),'U349':(44,117,0),'C298':(17,109,0),'C299':(33,109,0),'R298':(34,112,90),
           'C398':(37,109,0),'C399':(44,106,0),'R398':(49,104,90)}
    if args.functional_layout:
        from functional_layout import place
        bank_placements=place(board,footprints,imported,root_path,manifest,nets,add_track,ground_pad,args.prepack_output)
        from route_ignition_local import route as route_ignition
        ignition_routes=route_ignition(board,footprints,nets,add_track)
        unplaced=[]
    else:
        ignition_routes=[]
        for ref,(x,y,a) in fixed.items():
            if ref in footprints:footprints[ref].SetPosition(vec(x,y));footprints[ref].SetOrientationDegrees(a);placed.add(ref)
        bank_refs,bank_placements=place_output_banks(board,footprints) if args.grouped_outputs else (set(),[])
        placed|=bank_refs
        unplaced=place_candidate_domains(board,footprints,set(components)-placed)
    add_plane(board,nets)
    title=board.GetTitleBlock();title.SetTitle('Power8GDI routed subdomains / INCOMPLETE ENGINEERING REVIEW');title.SetRevision('A engineering candidate')
    label=p.PCB_TEXT(board);label.SetText('Power8GDI RevA - INCOMPLETE / DO NOT FABRICATE');label.SetPosition(vec(70,92));label.SetTextSize(vec(1.3,1.3));label.SetLayer(p.F_SilkS);board.Add(label)
    # Assign every source component and audit all pads before saving anything.
    actual=defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNumber(): actual[(fp.GetReference(),pad.GetNumber())].append(pad.GetNetname())
    errors=compare_pad_assignments(assignments,actual)
    if errors:raise ValueError('\n'.join(errors))
    silk_report=arrange_references(board)
    dest=out/'Power8GDI_Review.kicad_pcb';p.SaveBoard(str(dest),board);insert_stackup(dest);project_file(dest.with_suffix('.kicad_pro'))
    libs={'Power8GDI_Board':HERE/'Power8GDI_Board.pretty','Power8GDI_Core':design/'Power8GDI_Core.pretty','Power8GDI_GDI':design/'gdi/Power8GDI_GDI.pretty',
          'Power8GDI_Interfaces':design/'interfaces/Power8GDI_Interfaces.pretty','Power8GDI_GDIProtection':design/'gdi/Power8GDI_GDIProtection.pretty',
          'Power8GDI_Motor4':design/'motor4/Power8GDI_Motor4.pretty'}
    for comp in components.values():
        name=comp['footprint'].split(':')[0]
        if name not in libs:libs[name]=Path('/usr/share/kicad/footprints')/(name+'.pretty')
    entries=[]
    for name,path in sorted(libs.items()):
        uri='${KICAD9_FOOTPRINT_DIR}/'+path.name if str(path).startswith('/usr/share/') else '${KIPRJMOD}/'+os.path.relpath(path,out)
        entries.append(f'(lib(name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr "PCB builder source library"))')
    (out/'fp-lib-table').write_text('(fp_lib_table(version 7)'+''.join(entries)+')\n')
    print('Filling zones',flush=True)
    board=p.LoadBoard(str(dest));board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());board.BuildConnectivity()
    cleanup_report=remove_dangling(board)
    p.SaveBoard(str(dest),board)
    # SaveBoard persists the in-process project cache, which began with default
    # rules before our generated .pro existed. Write the authoritative project
    # AFTER the final save; otherwise KiCad overwrites .2 mm with its 0 mm default.
    project_file(dest.with_suffix('.kicad_pro'))
    report={'kicad_version':p.GetBuildVersion(),'qualification':'INCOMPLETE_ENGINEERING_REVIEW_DO_NOT_FABRICATE',
            'outline_mm':[245,165],'copper_layers':4,'thickness_mm':1.6,'source_netlists':sources,
            'source_reference_pcb_sha256':digest(args.source_board),'source_reference_mapping_sha256':digest(design/'gdi/reference_mapping.json'),
            'connector_pinout_sha256':digest(args.pinout),'connector_aliases':aliases,'components':len(components),
            'assigned_component_pins':len(assignments),'pad_net_mismatches':errors,'tracks_vias':len(list(board.GetTracks())),
            'zones':len(list(board.Zones())),'unconnected_count':board.GetConnectivity().GetUnconnectedCount(False),
            'dnp_references':sorted(ref for ref,comp in components.items() if comp['dnp']),
            'staged_unreviewed_placements':unplaced,'reference_copper':audit,
            'silkscreen_geometry':silk_report,'copper_cleanup':cleanup_report,'output_bank_placement':bank_placements,
            'ignition_local_routes':ignition_routes}
    (out/'board_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('reference_copper','source_netlists','staged_unreviewed_placements')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design-root',type=Path,default=HERE.parent)
    parser.add_argument('--source-board',type=Path,default=HERE.parents[3]/'GDI-4ch/GDI-4ch.kicad_pcb')
    parser.add_argument('--pinout',type=Path,default=HERE.parents[2]/'pinout/power8gdi_revA_pinout.csv')
    parser.add_argument('--output-dir',type=Path,default=HERE/'review')
    parser.add_argument('--grouped-outputs',action='store_true',help='Require four-channel LS banks to fit together; fail on current geometry conflicts')
    parser.add_argument('--functional-layout',action='store_true',default=True,help='Use functional regions within the original245x165 outline (default)')
    parser.add_argument('--legacy-placement',dest='functional_layout',action='store_false',help='Reproduce the obsolete staging placement for diagnosis only')
    parser.add_argument('--prepack-output',type=Path,help='Save unplaced diagnostic input and fixed-reference list for local module development')
    build(parser.parse_args())
