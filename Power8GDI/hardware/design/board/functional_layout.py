"""Functional regions inside the existing outline; actual pad/body obstacles.

This is a review floorplan, not electrical/thermal approval. All donor copper
is retained by the caller's audited transfer; placements cannot erase it.
"""
from collections import defaultdict
import math
import xml.etree.ElementTree as ET
import pcbnew as p
from build_connector import vec
from board_cleanup import Spatial


def box(fp,margin=.25):
    b=fp.GetBoundingBox(False,False)
    return (p.ToMM(b.GetX())-margin,p.ToMM(b.GetY())-margin,p.ToMM(b.GetRight())+margin,p.ToMM(b.GetBottom())+margin)


def move(fp,x,y,angle=0,back=False):
    if (fp.GetLayer()==p.B_Cu)!=back:fp.Flip(fp.GetPosition(),False)
    fp.SetOrientationDegrees(angle);fp.SetPosition(vec(x,y))


def place(board,fps,imported,netlist,manifest,nets,add_track,ground_pad):
    groups=defaultdict(list)
    for comp in ET.parse(netlist).findall('components/comp'):
        ref=comp.attrib['ref'];name=comp.find('sheetpath').get('names').strip('/')
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
        move(fps[f'R{n+7}'],x-4,y+8,0);placed.add(f'R{n+7}')
        move(fps[f'R{n+5}'],x-8,y-3,90);placed.add(f'R{n+5}')
        move(fps[f'R{n+6}'],x-8,y+3,90);placed.add(f'R{n+6}')
    # Register copper and component obstacles independently for each assembly side.
    occupied={p.F_Cu:Spatial(),p.B_Cu:Spatial()}
    copper_obstacles={p.F_Cu:Spatial(),p.B_Cu:Spatial()}
    for t in board.GetTracks():
        b=t.GetBoundingBox();r=(p.ToMM(b.GetX())-.3,p.ToMM(b.GetY())-.3,p.ToMM(b.GetRight())+.3,p.ToMM(b.GetBottom())+.3)
        for layer in occupied:
            if isinstance(t,p.PCB_VIA) or t.GetLayer()==layer:copper_obstacles[layer].add(r)
    for ref in placed:
        fp=fps[ref]
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
        if 'H-bridge' in name:return (75,5,151,52),(115,25),3
        if 'battery' in name or '3V3 logic' in name:return (5,5,72,52),(36,25),3
        if 'gdi/' in name or 'GDI bank' in name:return (5,5,151,55),(75,45),4
        if 'wbo' in name.lower():
            x=156 if 'wbo1' in name else 199
            return (x,83,x+40,142),(x+20,111),5
        if 'MCU' in name or 'permission' in name:return (5,94,48,142),(26,116),6
        if 'USB' in name or 'microSD' in name:return (5,5,72,55),(10,40),4
        return (156,5,239,82),(195,43),7
    # Within each functional group, place packages first and place passives near
    # already placed pins on their own low-fanout nets. No fallback off-board.
    refs_by_net=defaultdict(set)
    for fp in fps.values():
        for pad in fp.Pads():
            if pad.GetNetname():refs_by_net[pad.GetNetname()].add(fp.GetReference())
    for name,refs in sorted(groups.items(),key=lambda item:(region(item[0])[2],item[0])):
        pending=[ref for ref in refs if ref not in placed]
        if not pending:continue
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
                    padboxes.append((p.ToMM(pb.GetX())-b[0],p.ToMM(pb.GetY())-b[1],p.ToMM(pb.GetRight())-b[0],p.ToMM(pb.GetBottom())-b[1]))
                for yi in range(int(y0*2),int((y1-h)*2)+1):
                    y=yi/2
                    for xi in range(int(x0*2),int((x1-w)*2)+1):
                        x=xi/2;r=(x,y,x+w,y+h)
                        score=(x+w/2-target[0])**2+(y+h/2-target[1])**2
                        if best is not None and score>=best[0]:continue
                        if occupied[p.B_Cu].collides(r):continue
                        # Routes may pass under an insulated package body, but
                        # no new pad may touch retained donor copper/via annuli.
                        if any(copper_obstacles[p.B_Cu].collides((x+a,y+bb,x+c,y+d)) for a,bb,c,d in padboxes):continue
                        best=(score,x-b[0],y-b[1],angle,r)
            if best is None:
                raise ValueError(f'Functional region exhausted: {name}, {ref}, region{(x0,y0,x1,y1)}; no outline/DRC relaxation allowed')
            _,x,y,a,r=best;move(fp,x,y,a,True);occupied[p.B_Cu].add(r);placed.add(ref);own.append(ref)
        report.append({'domain':name,'region_mm':[x0,y0,x1,y1],'side':'B.Cu','references':own,'review':'Function-group placement with net-neighbor attraction; power-loop/EMC/thermal review remains open'})
    if set(fps)!=placed:raise ValueError('Unplaced references:'+str(sorted(set(fps)-placed)))
    return report
