"""Board outline and placement anchors as data; one profile per build.

The default profile reproduces the 245 x 165 working-outline constants that
were previously written inline in build_board.py and functional_layout.py.
A profile is a placement input, not routing, thermal or EMC evidence.

The donor GDI stage B copper, the single WBO local circuit (back side, under
stage B) and every reviewed WBO route share one frame. Moving stage B therefore
moves that whole frame by the same vector; rotating it is refused, because the
reviewed WBO routes and pad contracts were checked only in the original
orientation. Call configure(path) before building; unconfigured use keeps the
default profile so existing tests on the sealed candidate are unchanged.
"""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
DEFAULT=HERE/'layout_profiles/245x165.json'
# Stage B target and WBO region of the reviewed 245 x 165 candidate. All
# absolute WBO route coordinates in route_wbo_*.py are stated in this frame.
BASE_STAGE_B=(157.,2.)
BASE_STAGE_B_ANGLE=90
BASE_WBO1=(153.,52.)

_profile=None
_source=None


def configure(path=DEFAULT):
    global _profile,_source
    path=Path(path)
    data=json.loads(path.read_text())
    _validate(data)
    _profile=data;_source={'path':str(path),'name':data['name'],'outline_mm':data['outline_mm']}
    return dict(_source)


def profile():
    if _profile is None:configure()
    return _profile


def provenance():
    profile()
    return dict(_source)


def _validate(data):
    w,h=data['outline_mm']
    b=data['stages']['B']
    if b['angle_deg']!=BASE_STAGE_B_ANGLE:
        raise ValueError('Stage B rotation differs from the reviewed WBO frame; WBO routes would need a new review')
    shift=(b['target_mm'][0]-BASE_STAGE_B[0],b['target_mm'][1]-BASE_STAGE_B[1])
    # WBO placement uses a 0.5 mm grid and some route contracts compare exact
    # coordinates; half-millimetre shifts stay exact in binary floating point.
    if any(abs(v*2-round(v*2))>1e-9 for v in shift):
        raise ValueError(f'Stage B / WBO frame shift must be a multiple of 0.5 mm: {shift}')
    wbo=data['wbo_regions_mm']['1']
    if abs(wbo[0]-BASE_WBO1[0]-shift[0])>1e-9 or abs(wbo[1]-BASE_WBO1[1]-shift[1])>1e-9:
        raise ValueError('WBO1 region must move with stage B (shared reviewed frame)')
    rects=[data['logic_power_region_mm'],*data['wbo_regions_mm'].values(),*(r['rect_mm'] for r in data['regions'].values())]
    for x0,y0,x1,y1 in rects:
        if not (0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError(f'Region outside outline: {[x0,y0,x1,y1]}')
    for ref,(x,y) in data['connectors_mm'].items():
        if not (0<x<w and 0<y<h):raise ValueError(f'Connector {ref} outside outline')


def outline():
    return tuple(profile()['outline_mm'])


def frame_shift():
    """Translation of the stage B / WBO frame relative to the reviewed candidate."""
    t=profile()['stages']['B']['target_mm']
    return (t[0]-BASE_STAGE_B[0],t[1]-BASE_STAGE_B[1])


def at(x,y):
    """A reviewed WBO-frame coordinate in the configured board."""
    dx,dy=frame_shift()
    return (x+dx,y+dy)


def shifted(points):
    """Shift nested point tuples ((x,y) pairs of numbers); other items unchanged."""
    if isinstance(points,tuple):
        if len(points)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in points):
            return at(*points)
        return tuple(shifted(v) for v in points)
    return points


def region(name):
    """Functional region rect, anchor and priority for a schematic sheet name."""
    prof=profile();r=prof['regions']
    if name.startswith('Ignition ') and 'permission' not in name:
        ch=int(name.split()[1]);cells=prof['ignition_cells']
        (ox,oy),(px,py),cols=cells['origin_mm'],cells['pitch_mm'],cells['columns']
        # Cell rect starts 12 mm left and 10 mm above the D2PAK origin.
        x=ox-12+px*((ch-1)%cols);y=oy-10+py*((ch-1)//cols)
        return (x,y,x+px,y+py),(x+12,y+11),0
    def rule(key):
        e=r[key];return tuple(e['rect_mm']),tuple(e['anchor_mm']),e['priority']
    if name.startswith('Ignition permission'):return rule('ignition_permission')
    if 'low-side' in name.lower():return rule('low_side')
    if 'H-bridge' in name or name.startswith('motor4 '):return rule('motor')
    if 'battery' in name or '3V3 logic' in name or name.startswith('logic power'):return rule('logic_power')
    if name in ('gdi/protection b','GDI bank B reference candidate'):return rule('gdi_protection_b')
    if 'gdi/' in name or 'GDI bank' in name:return rule('gdi')
    if 'wbo' in name.lower():
        if 'wbo1' in name:
            x0,y0,x1,y1=prof['wbo_regions_mm']['1']
            return (x0,y0,x1,y1),((x0+x1)/2,y1-34),5
        return rule('wbo_other')
    if 'MCU' in name or 'permission' in name:return rule('mcu')
    if 'USB' in name or 'microSD' in name:return rule('usb_sd')
    if 'knock' in name.lower():return rule('knock')
    if 'sensor trackers' in name.lower():return rule('sensor_trackers')
    if name=='Hall and SENT receiver bank 2':return rule('hall_sent_bank2')
    # Quiet inputs may share unused space around the WBO analogue region;
    # actual placed bodies/pads remain hard obstacles on that same side.
    return rule('default')
