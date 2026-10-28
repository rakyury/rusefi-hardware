"""Small, explicit BOOT escape policy adjacent to TI RNP0030 pad 6 only."""
import pcbnew as p
from package_clearance import validate_lm76003

AREA='U5200_BOOT_ESCAPE'

def bounds(board):
    validate_lm76003(board)
    f=next(f for f in board.GetFootprints() if f.GetReference()=='U5200')
    if f.GetLayer()!=p.B_Cu or abs(f.GetOrientationDegrees()-90)>1e-6:
        raise ValueError('BOOT escape orientation changed; review local geometry')
    x,y=p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)
    return x-.15,y+1.70,x+.15,y+2.65

def permits(board,net,a,b,width,layer,obstacle):
    if net!='LP5_BOOT' or layer!=p.B_Cu or width>.2+1e-9 or obstacle not in ('U5200.5','U5200.7'):
        return False
    x0,y0,x1,y1=bounds(board)
    return all(x0<=x-width/2 and x+width/2<=x1 and y0<=y-width/2 and y+width/2<=y1 for x,y in (a,b))

def add_area(board):
    if any(z.GetIsRuleArea() and z.GetZoneName()==AREA for z in board.Zones()):
        raise ValueError('BOOT escape area already exists')
    x0,y0,x1,y1=bounds(board)
    z=p.ZONE(board);z.SetLayer(p.B_Cu);z.SetIsRuleArea(True);z.SetZoneName(AREA)
    z.SetDoNotAllowTracks(False);z.SetDoNotAllowVias(False);z.SetDoNotAllowCopperPour(False)
    z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
    poly=z.Outline();poly.NewOutline()
    for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
        poly.Append(p.FromMM(x),p.FromMM(y))
    board.Add(z)
    return {'name':AREA,'bounds_mm':[x0,y0,x1,y1],'track_clearance_mm':.25,'normal_clearance_mm':.3}

def rule_text():
    def term(a,b):
        return (f"{a}.Type == 'Track' && {a}.NetName == 'LP5_BOOT' && {a}.Width <= 0.2mm && "
                f"{a}.enclosedByArea('{AREA}') && {b}.Type == 'Pad' && "
                f"{b}.memberOfFootprint('U5200') && ({b}.Pad_Number == '5' || {b}.Pad_Number == '7')")
    return '(rule "TI RNP0030 bounded BOOT escape" (condition "('+term('A','B')+') || ('+term('B','A')+')") (constraint clearance (min 0.25mm)))\n'
