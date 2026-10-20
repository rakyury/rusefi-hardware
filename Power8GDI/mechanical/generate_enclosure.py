"""Power8GDI parametric enclosure MECHANICAL CONCEPT, not fabrication release.

CAD is based on a provisional 245 x 165 mm board *envelope* only.
NO connector cutouts, seal groove, actual component heatsinking or PCB holes validated.
Usage: python mechanical/generate_enclosure.py
"""
from pathlib import Path
import json
import cadquery as cq

OUT = Path(__file__).resolve().parent
CONFIG = {
    "units": "mm",
    "status": "CONCEPT_NOT_FOR_MANUFACTURING",
    "material_candidate": "Aluminum 6061-T6 (undecided)",
    "pcb_outline_nominal": [245.0, 165.0],
    "outer_dimensions": [265.0, 185.0, 54.0],
    "wall": 5.0,
    "base_height": 42.0,
    "base_floor": 5.0,
    "lid_height": 12.0,
    "standoff_height": 6.0,
    "standoff_diameter": 10.0,
    "standoff_pilot_diameter": 2.5,
    "lid_clearance_hole_diameter": 3.4,
    "mounts_x": [-114.0, 114.0],
    "mounts_y": [-74.0, 74.0],
    "connector_openings": "UNDEFINED - matching TE header and component positions pending",
    "sealing": "UNDEFINED - IP rating/gasket not verified",
    "thermal_coupling": "UNDEFINED - PCB component heights & heat paths unverified",
}

L, W, H = CONFIG["outer_dimensions"]
wall = CONFIG["wall"]
floor = CONFIG["base_floor"]
base_h = CONFIG["base_height"]
lid_h = CONFIG["lid_height"]
boss_h = CONFIG["standoff_height"]
mx = CONFIG["mounts_x"]
my = CONFIG["mounts_y"]
mounts = [(x,y) for x in mx for y in my]

# Base: milled open pocket, closed floor. The connector face is intentionally SOLID.
base = cq.Workplane("XY").rect(L, W).extrude(base_h)
base = base.faces(">Z").workplane().rect(L-2*wall, W-2*wall).cutBlind(-(base_h-floor))
for x,y in mounts:
    boss = cq.Workplane("XY").center(x,y).circle(CONFIG["standoff_diameter"]/2).extrude(floor+boss_h)
    base = base.union(boss)
    bore = cq.Workplane("XY").workplane(offset=floor).center(x,y).circle(CONFIG["standoff_pilot_diameter"]/2).extrude(boss_h)
    base = base.cut(bore)

# Concept lid: flat 12mm blank, openable, undrilled for perimeter fasteners.
# No gasket groove is added until ingress-protection and fastening requirements are known.
lid = cq.Workplane("XY").workplane(offset=base_h).rect(L,W).extrude(lid_h)

# Make mounting pilot holes visible on the lid for envelope alignment only.
# They are not final lid fastening provisions.
for x,y in mounts:
    marker = cq.Workplane("XY").workplane(offset=base_h).center(x,y).circle(CONFIG["lid_clearance_hole_diameter"]/2).extrude(lid_h)
    lid=lid.cut(marker)

# Export as individual STEP solids, plus assembly for mechanical envelope checks.
cq.exporters.export(base, str(OUT / "Power8GDI_Base_CONCEPT.step"))
cq.exporters.export(lid, str(OUT / "Power8GDI_Lid_CONCEPT.step"))
cq.exporters.export(cq.Compound.makeCompound([base.val(),lid.val()]),str(OUT / "Power8GDI_Enclosure_CONCEPT.step"))
(OUT / "enclosure_params.json").write_text(json.dumps(CONFIG,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
assert base.val().Volume() > 0
assert lid.val().Volume() > 0
assert (L-2*wall)>=CONFIG['pcb_outline_nominal'][0]
assert (W-2*wall)>=CONFIG['pcb_outline_nominal'][1]
print("concept STEP exports OK",round(base.val().Volume()),round(lid.val().Volume()),"mm^3")
