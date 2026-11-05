"""Derive a 0.3 mm drill candidate without changing the DDA package lands.

The six holes keep their original centres. Their annular lands increase to
0.6 mm; pad numbers, EP, lead lands, mask/paste and body remain unchanged.
PCB fabrication and solder-wicking qualification are still required.
"""
from pathlib import Path
import hashlib
import json
import pcbnew as p

HERE = Path(__file__).resolve().parent
SOURCE = Path('/usr/share/kicad/footprints/Package_SO.pretty')
SOURCE_NAME = 'HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm_ThermalVias'
NAME = 'HSOP8_EP_ThermalVia0p3'


def generate():
    plugin = p.PCB_IO_MGR.PluginFind(p.PCB_IO_MGR.KICAD_SEXP)
    fp = plugin.FootprintLoad(str(SOURCE), SOURCE_NAME)
    assert fp is not None
    changed = []
    for pad in fp.Pads():
        if pad.GetAttribute() != p.PAD_ATTRIB_PTH:
            continue
        assert pad.GetNumber() == '9'
        assert abs(p.ToMM(pad.GetDrillSize().x) - .2) < 1e-6
        pad.SetDrillSize(p.VECTOR2I(p.FromMM(.3), p.FromMM(.3)))
        pad.SetSize(p.VECTOR2I(p.FromMM(.6), p.FromMM(.6)))
        changed.append([p.ToMM(pad.GetPosition().x), p.ToMM(pad.GetPosition().y)])
    assert len(changed) == 6
    fp.SetFPID(p.LIB_ID('Power8GDI_Board', NAME))
    fp.SetLibDescription('DDA 8 lead EP2.41x3.1; original KiCad lands; six 0.3 drill / 0.6 land thermal holes; engineering candidate')
    destination = HERE / 'Power8GDI_Board.pretty'
    plugin.FootprintSave(str(destination), fp)
    (HERE / 'thermal_footprint_provenance.json').write_text(json.dumps({
        'source_library': 'KiCad 9.0.9 Package_SO',
        'source_footprint': SOURCE_NAME,
        'source_sha256': hashlib.sha256((SOURCE / (SOURCE_NAME + '.kicad_mod')).read_bytes()).hexdigest(),
        'license': 'KiCad libraries CC-BY-SA-4.0 with exception',
        'changed': 'Only six pad9 PTH holes: drill 0.2 to 0.3 mm, land 0.5 to 0.6 mm',
        'thermal_hole_centres_mm': changed,
        'minimum_annulus_mm': .15,
        'qualification': 'Candidate; fabrication and reflow qualification pending'
    }, indent=2) + '\n')


if __name__ == '__main__':
    generate()
