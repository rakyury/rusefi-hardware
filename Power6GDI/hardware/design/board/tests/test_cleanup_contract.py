"""Incomplete local breakout copper must survive generic donor cleanup."""
from pathlib import Path
import sys
import unittest
import pcbnew as p

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from board_cleanup import remove_dangling


class CleanupContract(unittest.TestCase):
    def test_explicit_local_breakout_is_kept_while_unprotected_tail_is_removed(self):
        board=p.BOARD()
        net=p.NETINFO_ITEM(board,'TEST_LOCAL_BREAKOUT');board.Add(net)
        items=[]
        for y in (0,10):
            t=p.PCB_TRACK(board);t.SetStart(p.VECTOR2I(p.FromMM(5),p.FromMM(y)))
            t.SetEnd(p.VECTOR2I(p.FromMM(8),p.FromMM(y)));t.SetWidth(p.FromMM(.25))
            t.SetLayer(p.F_Cu);t.SetNet(net);board.Add(t);items.append(t)
        keep=items[0].m_Uuid.AsString()
        result=remove_dangling(board,{keep})
        self.assertEqual([t.m_Uuid.AsString() for t in board.GetTracks()],[keep])
        self.assertEqual(len(result['dangling_tracks_removed']),1)
        self.assertEqual(result['protected_copper_items'],1)
