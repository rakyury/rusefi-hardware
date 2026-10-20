"""Electrical connectivity regressions, using real KiCad-exported XML netlists."""
from pathlib import Path
from copy import deepcopy
import csv
import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from sexpr import parse, children, child, prop, walk

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(stage):
    return ET.parse(HERE / ('stage_' + stage.lower() + '.xml'))


def nets(tree):
    return {n.attrib['name']: {(p.attrib['ref'], p.attrib['pin']) for p in n.findall('node')}
            for n in tree.findall('.//nets/net')}


def pin_nets(tree):
    return {p: name for name, pins in nets(tree).items() for p in pins}


def topology_errors(tree, stage):
    mapping = json.loads((HERE/'reference_mapping.json').read_text())[stage]['reference_map']
    source = json.loads((HERE/'source_pin_nets.json').read_text())['nets']
    actual = {name: {(r,p) for r,p in group if r in mapping.values()} for name,group in nets(tree).items()}
    lookup = {p:name for name,group in actual.items() for p in group}
    errors=[]
    for name,nodes in source.items():
        expected={(mapping[n['ref']],n['pin']) for n in nodes}
        found={lookup.get(p) for p in expected}
        if len(found)!=1 or None in found:
            errors.append(('split_or_missing',name));continue
        if actual[next(iter(found))]!=expected:
            errors.append(('short_or_extra',name))
    return errors


class SchematicTests(unittest.TestCase):
    def test_pinned_source_hash(self):
        data=(ROOT/'GDI-4ch/GDI-4ch.kicad_sch').read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(hashlib.sha256(data).hexdigest(),json.loads((HERE/'source_pin_nets.json').read_text())['source_schematic_lf_sha256'])
        for source in json.loads((HERE/'provenance.json').read_text())['sources']:
            data=(ROOT/source['path']).read_bytes().replace(b'\r\n',b'\n')
            self.assertEqual(hashlib.sha256(data).hexdigest(),source['lf_sha256'],source['path'])

    def test_all_reference_pin_connections_survive(self):
        for stage in 'AB':
            with self.subTest(stage=stage):self.assertEqual(topology_errors(load(stage),stage),[])

    def test_checker_detects_pin_short_and_break(self):
        tree=load('A'); node=tree.find('.//nets/net/node[@ref="U201"][@pin="25"]')
        parent=next(n for n in tree.findall('.//nets/net') if node in list(n))
        parent.remove(node)
        self.assertTrue(topology_errors(tree,'A'))
        tree=load('A');ns=tree.findall('.//nets/net');ns[0].extend(list(ns[1]));del ns[1][:]
        self.assertTrue(topology_errors(tree,'A'))

    def test_stage_references_and_independent_control_rails(self):
        a,b=load('A'),load('B')
        self.assertFalse({c.attrib['ref'] for c in a.findall('.//components/comp')} & {c.attrib['ref'] for c in b.findall('.//components/comp')})
        shared={n for n in nets(a).keys() & nets(b).keys() if not n.startswith('Net-')}
        self.assertEqual(shared,{'GND','+3V3','GDI_SPI2_MISO','GDI_SPI2_MOSI','GDI_SPI2_SCK'})
        for stage,base in [('A',200),('B',300)]:
            lookup=pin_nets(load(stage));u='U'+str(base+1)
            for pin,suffix in [('13','CS'),('3','RESET'),('2','DEVICE_DRVEN'),('10','FLAG')]:
                self.assertEqual(lookup[(u,pin)],'PT'+stage+'_'+suffix)
            self.assertEqual(lookup[(u,'21')],'+5V_GDI_'+stage)
            self.assertEqual(lookup[(u,'39')],'VBAT_GDI_'+stage)
            self.assertEqual(lookup[(u,'48')],'PT'+stage+'_VBOOST')

    def test_enable_isolation_dnp_not_a_short(self):
        for stage,base in [('A',200),('B',300)]:
            tree=load(stage);r='R'+str(base+99);c=tree.find('.//components/comp[@ref="'+r+'"]')
            self.assertIsNotNone(c.find('property[@name="dnp"]'))
            lookup=pin_nets(tree)
            self.assertEqual(lookup[(r,'1')],'PT'+stage+'_DRVEN')
            self.assertEqual(lookup[(r,'2')],'PT'+stage+'_DEVICE_DRVEN')
            self.assertNotEqual(lookup[(r,'1')],lookup[(r,'2')])

    def test_nxp_pin20_and_directions_corrected(self):
        for stage,base in [('A',200),('B',300)]:
            tree=load(stage);u='U'+str(base+1)
            self.assertEqual(tree.find('.//components/comp[@ref="'+u+'"]/value').text,'MC33PT2001AE')
            for pin,name,kind in [('20','VCC1P5','power_out'),('15','MISO','tri_state'),('10','FLAG0','bidirectional'),('3','RESETB','input')]:
                n=tree.find('.//nets/net/node[@ref="'+u+'"][@pin="'+pin+'"]')
                self.assertEqual((n.attrib['pinfunction'],n.attrib['pintype']),(name,kind))

    def test_every_electrical_pin_has_physical_pad(self):
        manifest=json.loads((HERE/'footprint_manifest.json').read_text())
        for stage in 'AB':
            tree=load(stage)
            for comp in tree.findall('.//components/comp'):
                lib,name=comp.findtext('footprint').split(':')
                self.assertEqual(lib,'Power8GDI_GDI')
                path=HERE/(lib+'.pretty')/(name+'.kicad_mod')
                self.assertEqual(hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),manifest[name.removeprefix('REF_')]['derived_footprint_sha256'])
                fp=parse(path.read_text())
                pads={p[1] for p in children(fp,'pad')}
                pins={p.attrib['pin'] for p in tree.findall('.//nets/net/node') if p.attrib['ref']==comp.attrib['ref']}
                self.assertFalse(pins-pads,(comp.attrib['ref'],pins-pads))

    def test_bom_and_export_are_consistent(self):
        with (HERE/'bom_reference.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),268)
        for stage in 'AB':
            tree=load(stage);actual={c.attrib['ref']:c for c in tree.findall('.//components/comp')}
            self.assertEqual(len(actual),134)
            for row in rows:
                if row['stage']!=stage:continue
                self.assertEqual(actual[row['reference']].findtext('value'),row['value'])
                self.assertEqual(actual[row['reference']].findtext('footprint'),row['footprint'])

    def test_local_regulator_connections(self):
        for stage,base in [('A',200),('B',300)]:
            lookup=pin_nets(load(stage));u='U'+str(base+49)
            self.assertEqual([lookup[(u,str(p))] for p in (1,2,3)],['VBAT_GDI_'+stage,'GND','+5V_GDI_'+stage])
            for ref,top in [('C'+str(base+98),'VBAT_GDI_'+stage),('C'+str(base+99),'+5V_GDI_'+stage),('R'+str(base+98),'+5V_GDI_'+stage)]:
                self.assertEqual(lookup[(ref,'1')],top)
                self.assertEqual(lookup[(ref,'2')],'GND')

    def test_hpfp_mapping_not_silently_assigned(self):
        for stage in 'AB':
            self.assertFalse({'HPFP1','HPFP2'} & nets(load(stage)).keys())

    def test_provenance_blocks_release(self):
        report=json.loads((HERE/'provenance.json').read_text())
        self.assertEqual(report['manufacturing_release'],'BLOCKED')
        self.assertGreaterEqual(len(report['blockers']),8)
        self.assertEqual(report['upstream_license_status'],'UNKNOWN')


if __name__=='__main__':unittest.main(verbosity=2)
