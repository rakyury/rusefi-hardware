"""Generate a TE drawing-derived 34-way header land pattern; requires pcbnew 9."""
from pathlib import Path
import pcbnew as p


def vec(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))


def through_layers():
    layers=p.LSET.AllCuMask()
    layers.AddLayer(p.F_Mask); layers.AddLayer(p.B_Mask)
    return layers


def make_footprint():
    fp = p.FOOTPRINT(None)
    fp.SetFPID(p.LIB_ID("Power8GDI_Board", "TE_6437288-1_34way"))
    fp.SetReference("J?")
    fp.SetValue("6437288-1")
    fp.SetAttributes(p.FP_THROUGH_HOLE)
    fp.SetLibDescription("TE C-9-1437287-8 Rev A1 sheet2; C-2-1437285-3 Rev P sheet3. Pin orientation requires physical continuity review before release.")
    # Component-side view; mate faces +Y. The header front/top orthographic
    # projections preserve X; the pins bend in Y/Z only. See PCB_CONNECTORS.md.
    pin = 1
    for count, start, y in [(9, -12, -14.5), (8, -10.5, -12), (8, -10.5, -9), (9, -12, -6.5)]:
        for column in range(count):
            pad = p.PAD(fp)
            pad.SetNumber(str(pin))
            pad.SetAttribute(p.PAD_ATTRIB_PTH)
            pad.SetShape(p.PAD_SHAPE_RECT if pin == 1 else p.PAD_SHAPE_CIRCLE)
            pad.SetSize(vec(2.2, 2.2))
            pad.SetDrillSize(vec(1.3, 1.3))
            pad.SetLayerSet(through_layers())
            pad.SetPosition(vec(start + column * 3, y))
            fp.Add(pad)
            pin += 1
    for x in (-19.25, 19.25):
        pad = p.PAD(fp)
        pad.SetAttribute(p.PAD_ATTRIB_NPTH)
        pad.SetShape(p.PAD_SHAPE_CIRCLE)
        pad.SetSize(vec(3.3, 3.3))
        pad.SetDrillSize(vec(3.3, 3.3))
        pad.SetLayerSet(through_layers())
        pad.SetPosition(vec(x, 0))
        fp.Add(pad)
    def line(a, b, layer, width):
        item = p.PCB_SHAPE(fp)
        item.SetShape(p.SHAPE_T_SEGMENT)
        item.SetStart(vec(*a)); item.SetEnd(vec(*b))
        item.SetWidth(p.FromMM(width)); item.SetLayer(layer)
        fp.Add(item)
    for layer, x0, x1, y0, y1 in [(p.F_Fab,-22.75,22.75,-17,19.5), (p.F_CrtYd,-23.25,23.25,-17.5,20)]:
        for a,b in [((x0,y0),(x1,y0)),((x1,y0),(x1,y1)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0))]:
            line(a,b,layer,0.05 if layer == p.F_CrtYd else 0.1)
    # Only on-board silhouette on silkscreen; front envelope remains on Fab.
    for a,b in [((-22.75,-3.5),(22.75,-3.5)),((-22.75,3.5),(22.75,3.5)),((-22.75,-3.5),(-22.75,3.5)),((22.75,-3.5),(22.75,3.5))]:
        line(a,b,p.F_SilkS,0.15)
    fp.Reference().SetPosition(vec(0,-19)); fp.Reference().SetTextSize(vec(1,1))
    fp.Value().SetPosition(vec(0,6)); fp.Value().SetLayer(p.F_Fab)
    return fp


if __name__ == "__main__":
    library = Path(__file__).resolve().parent / "Power8GDI_Board.pretty"
    library.mkdir(exist_ok=True)
    p.PCB_IO_MGR.PluginFind(p.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(library), make_footprint())
