"""Bounded LM76003 land-pattern policy; no track/via clearance relaxation.

TI RNP0030B/E example land patterns specify 0.5 mm pitch and 0.25 mm pad
width. Only the four battery-domain adjacent pairs on U5200 need a 0.25 mm
pad-to-pad target. Other copper retains the normal voltage-domain policy.
"""
import math

LM_FOOTPRINT='Package_DFN_QFN:Texas_RNP0030B_WQFN-30-1EP_4x6mm_P0.5mm_EP1.8x4.5mm'
LM_PAIRS=(('5','6'),('6','7'),('19','20'),('22','23'))


def validate_lm76003(board):
    import pcbnew as p
    fp=next(f for f in board.GetFootprints() if f.GetReference()=='U5200')
    if str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName())!=LM_FOOTPRINT:
        raise ValueError('U5200 package changed; re-review pad clearance policy')
    if fp.GetValue()!='LM76003QRNPRQ1':
        raise ValueError('U5200 device changed; re-review pad clearance policy')
    pads={q.GetNumber():q for q in fp.Pads() if q.GetNumber()}
    for a,b in LM_PAIRS:
        pa,pb=pads[a],pads[b]
        for q in (pa,pb):
            size=sorted((p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y)))
            if any(abs(x-y)>1e-6 for x,y in zip(size,(.25,1.025))):
                raise ValueError('U5200 land size changed')
        delta=pa.GetPosition()-pb.GetPosition()
        if abs(math.hypot(p.ToMM(delta.x),p.ToMM(delta.y))-.5)>1e-6:
            raise ValueError('U5200 land pitch changed')
        if pa.GetOrientationDegrees()!=pb.GetOrientationDegrees():
            raise ValueError('U5200 adjacent pad orientation changed')
    return {'reference':'U5200','pad_pairs':LM_PAIRS,'minimum_mm':.25,
            'scope':'Only these intrinsic pad-to-pad pairs; no track/via override'}


def lm76003_rule_text():
    lines=[]
    for a,b in LM_PAIRS:
        pair=f"((A.Pad_Number == '{a}' && B.Pad_Number == '{b}') || (A.Pad_Number == '{b}' && B.Pad_Number == '{a}'))"
        condition="A.Type == 'Pad' && B.Type == 'Pad' && A.memberOfFootprint('U5200') && B.memberOfFootprint('U5200') && "+pair
        lines.append(f'(rule "TI RNP0030 land pair {a}-{b}" (condition "{condition}") (constraint clearance (min 0.25mm)))')
    return '\n'.join(lines)+'\n'
