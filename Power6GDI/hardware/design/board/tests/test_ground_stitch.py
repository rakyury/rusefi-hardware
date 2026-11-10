"""Ground stitching contract on a synthetic board (pcbnew required)."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import pcbnew as p
import layout_profile
import ground_stitch
from route_wbo_local import vec


def smd_pad(board,ref,net,x,y,size=(1.0,1.0),layer=p.F_Cu):
    fp=p.FOOTPRINT(board);fp.SetReference(ref);fp.SetPosition(vec(x,y));board.Add(fp)
    pad=p.PAD(fp);pad.SetNumber('1');pad.SetAttribute(p.PAD_ATTRIB_SMD);pad.SetShape(p.PAD_SHAPE_RECT)
    pad.SetSize(p.VECTOR2I(p.FromMM(size[0]),p.FromMM(size[1])));pad.SetPosition(vec(x,y))
    ls=p.LSET()
    for l in (p.F_Cu,p.F_Mask,p.F_Paste):ls.AddLayer(l)  # front; Flip below moves it to the back
    pad.SetLayerSet(ls);pad.SetNet(net);fp.Add(pad)
    if layer==p.B_Cu:fp.Flip(fp.GetPosition(),False)
    return pad


def make_board():
    board=p.BOARD();board.GetDesignSettings().SetCopperLayerCount(4)
    nets={}
    for name in ('GND','SIG','HARNESS_IGN1'):
        n=p.NETINFO_ITEM(board,name);board.Add(n);nets[name]=n
    for a,b in [((0,0),(40,0)),((40,0),(40,30)),((40,30),(0,30)),((0,30),(0,0))]:
        e=p.PCB_SHAPE(board);e.SetShape(p.SHAPE_T_SEGMENT);e.SetStart(vec(*a));e.SetEnd(vec(*b));e.SetLayer(p.Edge_Cuts);board.Add(e)
    zone=p.ZONE(board);zone.SetLayer(p.In1_Cu);zone.SetNet(nets['GND']);zone.SetPadConnection(p.ZONE_CONNECTION_FULL)
    poly=zone.Outline();poly.NewOutline()
    for x,y in [(1,1),(39,1),(39,29),(1,29)]:poly.Append(p.FromMM(x),p.FromMM(y))
    board.Add(zone)
    return board,nets


class GroundStitchTests(unittest.TestCase):
    def setUp(self):layout_profile.configure(HERE/'layout_profiles/245x165.json')

    def fill(self,board):
        # ZONE_FILLER segfaults on an in-memory board (KiCad 9 SWIG); save and reload like build_board does.
        path=Path(tempfile.mkdtemp())/'mini.kicad_pcb';p.SaveBoard(str(path),board)
        board=p.LoadBoard(str(path));board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());board.BuildConnectivity()
        return board

    def test_island_gets_one_via_and_reaches_plane(self):
        board,nets=make_board()
        smd_pad(board,'C1',nets['GND'],10,10);smd_pad(board,'C2',nets['GND'],30,20,layer=p.B_Cu)
        board=self.fill(board)
        report=ground_stitch.stitch(board)
        self.assertEqual((report['islands'],report['stitched'],report['unstitched']),(2,2,[]))
        board=self.fill(board)
        plane,remaining=ground_stitch.islands(board)
        self.assertEqual((len(plane),remaining),(2,[]))
        vias=[t for t in board.GetTracks() if t.Type()==p.PCB_VIA_T]
        self.assertEqual(len(vias),2)
        self.assertTrue(all(v.GetNetname()=='GND' for v in vias))
        layers={t.GetLayer() for t in board.GetTracks() if t.Type()!=p.PCB_VIA_T}
        self.assertEqual(layers,{p.F_Cu,p.B_Cu})

    def test_hv_neighbour_blocks_the_via_instead_of_forcing_it(self):
        board,nets=make_board()
        pad=smd_pad(board,'C1',nets['GND'],20,15)
        # Ring of HARNESS_IGN1 copper 3 mm from the pad: 2.5 mm clearance leaves no room inside,
        # and any via outside the ring needs a stub that crosses it.
        for a,b in [((17,12),(23,12)),((23,12),(23,18)),((23,18),(17,18)),((17,18),(17,12))]:
            t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetWidth(p.FromMM(.5));t.SetLayer(p.F_Cu);t.SetNet(nets['HARNESS_IGN1']);board.Add(t)
        board=self.fill(board)
        report=ground_stitch.stitch(board)
        self.assertEqual(report['stitched'],0)
        self.assertEqual(report['unstitched'][0]['pads'],['C1.1'])
        self.assertFalse([t for t in board.GetTracks() if t.GetNetname()=='GND'])

    def test_already_connected_pad_is_not_touched(self):
        board,nets=make_board()
        pad=smd_pad(board,'C1',nets['GND'],10,10)
        t=p.PCB_TRACK(board);t.SetStart(vec(10,10));t.SetEnd(vec(12,10));t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNet(nets['GND']);board.Add(t)
        v=p.PCB_VIA(board);v.SetPosition(vec(12,10));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(nets['GND']);board.Add(v)
        board=self.fill(board)
        report=ground_stitch.stitch(board)
        self.assertEqual((report['plane_pads'],report['islands'],report['stitched']),(1,0,0))


if __name__=='__main__':
    unittest.main()
