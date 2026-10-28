from pathlib import Path
from copy import deepcopy
import json
import sys
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'gdi'))
from load_review import validate,footprint_errors,stencil_errors,SHUNT_SOURCE_REFS
from sexpr import parse,child,children

class LoadReview(unittest.TestCase):
    def setUp(self):
        self.root=ET.parse(HERE/'core.net').getroot()
        self.contract=json.loads((HERE/'gdi/scheduling_contract.json').read_text())
    def test_actual_netlist_shared_paths(self):self.assertEqual(validate(self.root,self.contract),[])
    def test_reject_wrong_kelvin_connection(self):
        n=self.root.find("nets/net/node[@ref='U201'][@pin='26']");n.set('pin','27')
        self.assertTrue(validate(self.root,self.contract))
    def test_reject_unsafe_overlap_contract(self):
        for field,value in [('max_simultaneously_active',2),('channels',[1,3])]:
            c=deepcopy(self.contract);c['shared_current_paths'][0][field]=value
            self.assertTrue(validate(self.root,c))
        c=deepcopy(self.contract);c['engine_permission']=True;self.assertTrue(validate(self.root,c))
    def test_reject_shunt_whole_device_net_tie(self):
        fp=parse((HERE/'gdi/Power8GDI_GDI.pretty/REF_R12.kicad_mod').read_text())
        self.assertEqual(footprint_errors(fp,True),[])
        child(fp,'net_tie_pad_groups')[1:]=['1,2,3,4']
        self.assertTrue(footprint_errors(fp,True))
    def test_mosfet_manufacturer_land_pattern(self):
        fp=parse((HERE/'gdi/Power8GDI_GDI.pretty/REF_Q1.kicad_mod').read_text())
        self.assertEqual(footprint_errors(fp),[])
        next(p for p in fp if isinstance(p,list) and p[0]=='pad' and p[1]=='1')[1]='3'
        self.assertTrue(footprint_errors(fp))
    def test_all_shunt_stencil_layers_and_mutations(self):
        for ref in SHUNT_SOURCE_REFS:
            original=parse((HERE/'gdi/Power8GDI_GDI.pretty'/f'REF_{ref}.kicad_mod').read_text())
            self.assertEqual(stencil_errors(original),[],ref)
            for number in ('1','4'):
                fp=deepcopy(original)
                pad=next(p for p in children(fp,'pad') if p[1]==number)
                child(pad,'layers').remove('F.Paste')
                self.assertTrue(stencil_errors(fp),(ref,number))
            for number in ('2','3'):
                fp=deepcopy(original)
                pad=next(p for p in children(fp,'pad') if p[1]==number)
                child(pad,'layers').append('F.Paste')
                self.assertTrue(stencil_errors(fp),(ref,number))
    def test_actual_board_shunts_have_stencil(self):
        board=parse((HERE/'board/gdi6_candidate/Power8GDI_Review.kicad_pcb').read_text())
        checked=[]
        for fp in children(board,'footprint'):
            if fp[1] not in {'Power8GDI_GDI:REF_'+r for r in SHUNT_SOURCE_REFS}:continue
            ref=next(p[2] for p in children(fp,'property') if p[1]=='Reference')
            checked.append(ref)
            self.assertEqual(stencil_errors(fp),[],ref)
        self.assertEqual(set(checked),{f'R{b+n}' for b in (200,300) for n in (3,12,13,15,21)})

if __name__=='__main__':unittest.main()
