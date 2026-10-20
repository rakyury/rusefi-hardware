"""Power8GDI Rev A envelope CAD - NOT manufacturing approved.

Independent CAD models are exported for base, lid, bare board, placeholder
components, 4 x 34-pin TE envelope-only shells and the full assembly.
No genuine TE geometry, thread/tolerance stack, internal PCB copper or thermal
validation is represented.
"""
from __future__ import annotations
import json
from pathlib import Path
import cadquery as cq

HERE = Path(__file__).resolve().parent
(HERE / 'stl').mkdir(exist_ok=True)

P = dict(
    pcb_x=245.0, pcb_y=165.0, pcb_thickness=1.6,
    housing_x=265.0, housing_y=185.0, base_z=42.0, lid_z=12.0,
    wall=5.0, floor=5.0, pcb_bottom_z=11.0,
    connector_width=49.0, connector_depth=44.0,
    connector_bottom_z=14.0, connector_height=23.0,
    connector_x=(-90.0,-30.0,30.0,90.0),
    connector_y=-88.5,
    screw_x=124.0, screw_y=84.0,
    m3_clearance=3.4,
    concept_only=True,
)

def box(x,y,z,xyz):
    return cq.Workplane('XY').box(x,y,z,centered=(True,True,False)).translate(xyz)

def cyl(r,h,x,y,z):
    return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z))

# Open milled base and perimeter fastener bosses.
base=box(P['housing_x'],P['housing_y'],P['base_z'],(0,0,0))
pocket=box(P['housing_x']-2*P['wall'],P['housing_y']-2*P['wall'],P['base_z']-P['floor']+.5,(0,0,P['floor']))
base=base.cut(pocket)
for x in (-P['screw_x'],P['screw_x']):
    for y in (-P['screw_y'],P['screw_y']):
        # Cylindrical pillar for M3 screws in base; pilot is a nominal
        # envelope and NOT manufacturing threads.
        base=base.union(cyl(5.9, P['base_z']-P['floor'],x,y,P['floor']))
        base=base.cut(cyl(1.25, P['base_z']-10,x,y,10))
# PCB support standoffs at board corners, not connected to outer mounting pillars.
mounts=[(x,y) for x in (-114.0,114.0) for y in (-74.0,74.0)]
for x,y in mounts:
    base=base.union(cyl(5.0,P['pcb_bottom_z']-P['floor'],x,y,P['floor']))
    base=base.cut(cyl(1.25,P['pcb_bottom_z']-P['floor']+.1,x,y,P['floor']))

# Four nominal connector openings through front wall. Actual apertures must
# be replaced by validated TE step model / gasket interface geometry.
for x in P['connector_x']:
    opening=box(P['connector_width']+1.0, P['wall']+2.0,
                P['connector_height']+1.0,
                (x,-P['housing_y']/2 + P['wall']/2,
                 P['connector_bottom_z']-.5))
    base=base.cut(opening)

# Lid is removable, with nominal through holes over four bosses.
lid=box(P['housing_x'],P['housing_y'],P['lid_z'],(0,0,P['base_z']))
for x in (-P['screw_x'],P['screw_x']):
    for y in (-P['screw_y'],P['screw_y']):
        lid=lid.cut(cyl(P['m3_clearance']/2,P['lid_z'],x,y,P['base_z']))
# PCB envelope, holes line up with standoffs.
pcb=box(P['pcb_x'],P['pcb_y'],P['pcb_thickness'],(0,0,P['pcb_bottom_z']))
for x,y in mounts:
    pcb=pcb.cut(cyl(1.7,P['pcb_thickness']+.2,x,y,P['pcb_bottom_z']-.1))

# Simplified mock components FOR SPACE PLANNING ONLY.
parts={}
for name, (w,h,z,x,y) in {
    'MCU_F7':(23,23,3,0,22),
    'PT2001_A':(21,21,5,-55,24),
    'PT2001_B':(21,21,5,55,24),
    'GDI_BOOST_A':(32,19,12,-60,59),
    'GDI_BOOST_B':(32,19,12,60,59),
    'LOW_SIDE_24':(50,15,4,0,65),
    'H_BRIDGE_A':(19,14,3,-90,0),
    'H_BRIDGE_B':(19,14,3,90,0),
    'KNOCK_ANALOG':(31,17,4,0,-29),
    'POWER_IN':(26,17,12,101,57),
    'LIN_CAN':(22,16,4,101,-39),
}.items():
    parts[name] = box(w,h,z,(x,y,P['pcb_bottom_z']+P['pcb_thickness']))

# Nominal 34-pin connector volume. Typical geometry, not TE product CAD.
connectors={}
for i,x in enumerate(P['connector_x']):
    main=box(P['connector_width'],P['connector_depth'],P['connector_height'],
             (x,P['connector_y'],P['connector_bottom_z']))
    # Recess-facing 34 cavities (17x2) on front face (approximate spacing).
    # Simplified shape retained separately to keep manageable CAD size.
    slots=[]
    for row in range(2):
        for col in range(17):
            slots.append(box(1.6,3.0,2.5,
                  (x+(col-8)*2.65,P['connector_y']-P['connector_depth']/2-.01,
                   P['connector_bottom_z']+6.2+row*8.2)))
    for slot in slots: main=main.cut(slot)
    connectors[f'J_{"ABCD"[i]}_34PIN_ENVELOPE']=main

# As-installed: connectors protrude through side openings; lid over them.
shapes={'Base':base,'Lid':lid,'PCB':pcb,**parts,**connectors}
for name,obj in shapes.items():
    cq.exporters.export(obj,str(HERE/'stl'/f'{name}.stl'))
for name,obj in [('Power8GDI_Base_PRELIM',base),('Power8GDI_Lid_PRELIM',lid),
                 ('Power8GDI_PCB_ENVELOPE',pcb),
                 ('Power8GDI_Connectors_ENVELOPE',cq.Compound.makeCompound([c.val() for c in connectors.values()]))]:
    cq.exporters.export(obj,str(HERE/f'{name}.step'))
compound=cq.Compound.makeCompound([obj.val() for obj in shapes.values()])
cq.exporters.export(compound,str(HERE/'Power8GDI_Assembly_PRELIM.step'))

# Exploded visualization source uses saved standalone solids; real assembly stays unshifted.
(HERE/'assembly_manifest.json').write_text(json.dumps({
    'status':'PRELIMINARY_CLEARANCE_ENVELOPE_ONLY',
    'warning':'Connector representations are NOT manufacturer STEP, and PCB has no copper or finished components.',
    'units':'mm','parameters':P,'pcb_mounts':mounts,
    'solids':list(shapes),'geometry_fidelity':{k:('envelope' if ('34PIN' in k or k=='PCB' or k in parts) else 'concept CAD') for k in shapes}
},indent=2),encoding='utf-8')
print('Parts',len(shapes),'assembly STEP MB',round((HERE/'Power8GDI_Assembly_PRELIM.step').stat().st_size/1e6,2))
