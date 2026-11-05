"""Mutation checks against the actual KiCad export, not a synthetic copied graph."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("verify_core",HERE/"verify_core.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConnectivityTests(unittest.TestCase):
    def check_mutation(self,mutator):
        tree=ET.parse(HERE/"core.net")
        mutator(tree.getroot())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"mutant.xml"
            tree.write(path)
            return module.verify(path)

    def test_real_kicad_export(self):
        result=module.verify(HERE/"core.net")
        self.assertEqual(result["errors"],[])
        self.assertEqual(result["release_status"],"BLOCKED")

    def test_vcap_external_load_is_rejected(self):
        def mutation(root):
            net=next(n for n in root.findall("nets/net") if n.get("name")=="MCU_VCAP_1")
            ET.SubElement(net,"node",ref="UNREVIEWED",pin="1")
        self.assertTrue(self.check_mutation(mutation)["errors"])

    def test_reversed_supply_pad_is_rejected(self):
        def mutation(root):
            for node in root.findall("nets/net/node"):
                if node.get("ref")=="U5200" and node.get("pin")=="20": node.set("pin","1")
        self.assertTrue(self.check_mutation(mutation)["errors"])

    def test_parallel_legacy_regulator_is_rejected(self):
        def mutation(root):
            comp=ET.SubElement(root.find('components'),'comp',ref='U102')
            ET.SubElement(comp,'value').text='TLV1117LV33DCYR'
            ET.SubElement(comp,'footprint').text='Package_TO_SOT_SMD:SOT-223-3_TabPin2'
        self.assertTrue(self.check_mutation(mutation)['errors'])

    def test_ignition_collector_swapped_to_gate_is_rejected(self):
        def mutation(root):
            node=root.find("nets/net/node[@ref='Q5420'][@pin='2']")
            node.set('pin','1')
        self.assertTrue(self.check_mutation(mutation)["errors"])

    def test_incompatible_root_tvs_is_rejected(self):
        def mutation(root): root.find("components/comp[@ref='D5201']/value").text="SMBJ33CA"
        self.assertTrue(self.check_mutation(mutation)["errors"])


if __name__=="__main__": unittest.main()
