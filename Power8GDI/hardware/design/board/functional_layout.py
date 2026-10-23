"""Functional regions inside the existing outline; actual pad/body obstacles.

This is a review floorplan, not electrical/thermal approval. All donor copper
is retained by the caller's audited transfer; placements cannot erase it.
"""
from collections import defaultdict
import math
import json
import xml.etree.ElementTree as ET
import pcbnew as p
from build_connector import vec
from board_cleanup import Spatial
import voltage_domains


def box(fp,margin=.25):
    b=fp.GetBoundingBox(False,False)
    return (p.ToMM(b.GetX())-margin,p.ToMM(b.GetY())-margin,p.ToMM(b.GetRight())+margin,p.ToMM(b.GetBottom())+margin)


def move(fp,x,y,angle=0,back=False):
    if (fp.GetLayer()==p.B_Cu)!=back:fp.Flip(fp.GetPosition(),False)
    fp.SetOrientationDegrees(angle);fp.SetPosition(vec(x,y))


def place(board,fps,imported,netlist,manifest,nets,add_track,ground_pad,prepack_output=None):
    groups=defaultdict(list)
    for comp in ET.parse(netlist).findall('components/comp'):
        ref=comp.attrib['ref'];name=comp.find('sheetpath').get('names').strip('/')
        # Reserve bulk parts before small analogue/control parts of the same
        # module. Sheet order must not consume its only capacitor footprint.
        if name.startswith('wbo/wbo'):name=name.split()[0]+' module'
        if name.startswith('motor4/'):name='motor4 complete bank'
        if name.startswith('logic power/'):name='logic power complete supply'
        if ref not in imported:groups[name].append(ref)
    placed=set(imported);report=[]
    for ref,x in [('J601',37),('J602',85),('J603',133),('J604',208)]:
        move(fps[ref],x,161.5);placed.add(ref)
    # MCU on quiet left-front, leaving the remaining lower-front for ignition.
    move(fps['U101'],28,116);placed.add('U101')
    for entry in manifest['decoupling_placement']:
        ref=entry['reference'];cap=fps[ref]
        pad=next(q for q in fps['U101'].Pads() if q.GetNumber()==entry['mcu_pad'])
        x,y=p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y)
        if abs(x-28)>abs(y-116):
            sign=1 if x>28 else -1;move(cap,x+sign*3,y,0 if sign>0 else 180);out=(sign,0)
        else:
            sign=1 if y>116 else -1;move(cap,x,y+sign*3,270 if sign>0 else 90);out=(0,sign)
        a=next(q for q in cap.Pads() if q.GetNumber()=='1');g=next(q for q in cap.Pads() if q.GetNumber()=='2')
        add_track(board,nets[pad.GetNetname()],[(x,y),(p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y))],.25)
        ground_pad(board,g,nets,out);placed.add(ref)
    # Eight D2PAK power cells, two rows. Gate at left, emitter below left;
    # shunt sits immediately below emitter, with sense comparator on reverse.
    for ch in range(1,9):
        n=5420+(ch-1)*20;x=61+24*((ch-1)%4);y=101+23*((ch-1)//4)
        move(fps[f'Q{n}'],x,y);placed.add(f'Q{n}')
        move(fps[f'R{n+7}'],x-8,y+10,0);placed.add(f'R{n+7}')
        # TO-263 lead centres are -7.65 mm from package origin: putting a
        # resistor at -8 mm overlays the actual gate/emitter lands.
        move(fps[f'R{n+5}'],x-13,y-2.54,0);placed.add(f'R{n+5}')
        move(fps[f'R{n+6}'],x-13,y+1,270);placed.add(f'R{n+6}')
    if prepack_output:
        prepack_output.parent.mkdir(parents=True,exist_ok=True)
        p.SaveBoard(str(prepack_output),board)
        prepack_output.with_suffix('.fixed.json').write_text(json.dumps({'status':'UNPLACED_DIAGNOSTIC_INPUT_ONLY','fixed_references':sorted(placed)},indent=2)+'\n')
    # Switching supply geometry owns the first choice of free space. Generic
    # area packing cannot substitute for Cin/IC/L/Cout loop placement.
    from route_logic_power_local import place_and_route as logic_power
    supply=logic_power(board,fps,nets,placed,region=(5,5,151,55))
    if any(c.get('anchor_mm') is None for c in supply['cells'].values()):
        raise ValueError('Compact logic supply placement failed: '+str(supply))
    placed.update(supply['placed_references']);report.append({'domain':'compact logic supply','local_module':supply})
    from route_wbo_local import place_and_route as wbo_local
    wbo=wbo_local(board,fps,nets,placed,regions={1:(153,52,197,142),2:(198,52,242,142)})
    placed.update(wbo['placed_references']);report.append({'domain':'dual WBO local circuits','local_module':wbo})
    # Register copper and component obstacles independently for each assembly side.
    occupied={p.F_Cu:Spatial(),p.B_Cu:Spatial()}
    copper_obstacles={layer:Spatial() for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)}
    for t in board.GetTracks():
        margin=max(.3,voltage_domains.clearance_mm(t.GetNetname()))
        b=t.GetBoundingBox();r=(p.ToMM(b.GetX())-margin,p.ToMM(b.GetY())-margin,p.ToMM(b.GetRight())+margin,p.ToMM(b.GetBottom())+margin)
        for layer in copper_obstacles:
            if t.IsOnLayer(layer):copper_obstacles[layer].add(r)
    def register_pads(fp):
        for pad in fp.Pads():
            pb=pad.GetBoundingBox()
            margin=max(.3,voltage_domains.clearance_mm(pad.GetNetname()))
            rect=(p.ToMM(pb.GetX())-margin,p.ToMM(pb.GetY())-margin,p.ToMM(pb.GetRight())+margin,p.ToMM(pb.GetBottom())+margin)
            for layer in copper_obstacles:
                if pad.IsOnLayer(layer):copper_obstacles[layer].add(rect)
    for ref in placed:
        fp=fps[ref]
        register_pads(fp)
        for layer in occupied:
            if fp.GetLayer()==layer:occupied[layer].add(box(fp))
            elif any(q.GetAttribute()==p.PAD_ATTRIB_PTH for q in fp.Pads()):
                for pad in fp.Pads():
                    if pad.GetAttribute() not in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH):continue
                    b=pad.GetBoundingBox();occupied[layer].add((p.ToMM(b.GetX())-.3,p.ToMM(b.GetY())-.3,p.ToMM(b.GetRight())+.3,p.ToMM(b.GetBottom())+.3))
    # Named domains; future sheet titles match by function, not numeric ref hacks.
    def region(name):
        if name.startswith('Ignition ') and 'permission' not in name:
            ch=int(name.split()[1]);x=49+24*((ch-1)%4);y=91+23*((ch-1)//4)
            return (x,y,x+24,y+23),(x+12,y+11),0
        if name.startswith('Ignition permission'):return (49,91,151,142),(99,113),1
        if 'low-side' in name.lower():return (5,55,151,92),(75,75),2
        if 'H-bridge' in name or name.startswith('motor4 '):return (5,5,151,55),(110,25),3
        if 'battery' in name or '3V3 logic' in name or name.startswith('logic power'):return (5,5,58,52),(30,25),3
        if name in ('gdi/protection b','GDI bank B reference candidate'):return (156,5,239,52),(190,24),4
        if 'gdi/' in name or 'GDI bank' in name:return (5,5,151,55),(75,45),4
        if 'wbo' in name.lower():
            x=153 if 'wbo1' in name else 198
            return (x,52,x+44,142),(x+22,108),5
        if 'MCU' in name or 'permission' in name:return (5,94,48,142),(26,116),6
        if 'USB' in name or 'microSD' in name:return (5,94,48,142),(12,103),0
        if 'knock' in name.lower():return (156,5,239,82),(220,18),6
        if 'sensor trackers' in name.lower():return (156,5,239,142),(216,45),6
        if name=='Hall and SENT receiver bank 2':return (146,94,155,142),(151,116),7
        # Quiet inputs may share unused space around the WBO analogue region;
        # actual placed bodies/pads remain hard obstacles on that same side.
        return (156,5,239,142),(195,28),7
    # Within each functional group, place packages first and place passives near
    # already placed pins on their own low-fanout nets. No fallback off-board.
    refs_by_net=defaultdict(set)
    for fp in fps.values():
        for pad in fp.Pads():
            if pad.GetNetname():refs_by_net[pad.GetNetname()].add(fp.GetReference())
    for name,refs in sorted(groups.items(),key=lambda item:(region(item[0])[2],item[0])):
        pending=[ref for ref in refs if ref not in placed]
        if not pending:continue
        print(f'Functional region: {name} ({len(pending)} remaining)',flush=True)
        (x0,y0,x1,y1),anchor,priority=region(name)
        pending.sort(key=lambda ref:-(box(fps[ref],0)[2]-box(fps[ref],0)[0])*(box(fps[ref],0)[3]-box(fps[ref],0)[1]))
        own=[]
        for ref in pending:
            fp=fps[ref];targets=[]
            for pad in fp.Pads():
                net=pad.GetNetname()
                if not net or net=='GND' or net.startswith(('+','VBAT','unconnected')) or len(refs_by_net[net])>10:continue
                for otherref in refs_by_net[net]&placed:
                    if otherref in imported:continue
                    for other in fps[otherref].Pads():
                        if other.GetNetname()==net:targets.append((p.ToMM(other.GetPosition().x),p.ToMM(other.GetPosition().y)))
            target=(sum(x for x,y in targets)/len(targets),sum(y for x,y in targets)/len(targets)) if targets else anchor
            best=None
            for angle in (0,90):
                move(fp,0,0,angle,True);b=box(fp);w,h=b[2]-b[0],b[3]-b[1]
                padboxes=[]
                for pad in fp.Pads():
                    pb=pad.GetBoundingBox()
                    for layer in copper_obstacles:
                        if pad.IsOnLayer(layer):
                            padboxes.append((layer,p.ToMM(pb.GetX())-b[0],p.ToMM(pb.GetY())-b[1],p.ToMM(pb.GetRight())-b[0],p.ToMM(pb.GetBottom())-b[1]))
                xs=sorted(range(int(x0*2),int((x1-w)*2)+1),key=lambda i:(abs(i/2+w/2-target[0]),i))
                ys=sorted(range(int(y0*2),int((y1-h)*2)+1),key=lambda i:(abs(i/2+h/2-target[1]),i))
                for yi in ys:
                    y=yi/2;dy2=(y+h/2-target[1])**2
                    if best is not None and dy2>best[0]:break
                    for xi in xs:
                        x=xi/2;r=(x,y,x+w,y+h)
                        score=(x+w/2-target[0])**2+dy2
                        if best is not None and score>best[0]:break
                        key=(score,angle,y,x)
                        if best is not None and key>=best[5]:continue
                        if occupied[p.B_Cu].collides(r):continue
                        # Routes may pass under an insulated package body, but
                        # no new pad may touch retained donor copper/via annuli.
                        if any(copper_obstacles[layer].collides((x+a,y+bb,x+c,y+d)) for layer,a,bb,c,d in padboxes):continue
                        best=(score,x-b[0],y-b[1],angle,r,key)
                        # All later X candidates on this row have no smaller
                        # distance; further rows are bounded by dy2 above.
                        break
            if best is None:
                raise ValueError(f'Functional region exhausted: {name}, {ref}, region{(x0,y0,x1,y1)}; no outline/DRC relaxation allowed')
            _,x,y,a,r,_=best;move(fp,x,y,a,True);occupied[p.B_Cu].add(r);register_pads(fp);placed.add(ref);own.append(ref)
        report.append({'domain':name,'region_mm':[x0,y0,x1,y1],'side':'B.Cu','references':own,'review':'Function-group placement with net-neighbor attraction; power-loop/EMC/thermal review remains open'})
    if set(fps)!=placed:raise ValueError('Unplaced references:'+str(sorted(set(fps)-placed)))
    return report
