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
                if node.get("ref")=="U102" and node.get("pin")=="3": node.set("pin","1")
        self.assertTrue(self.check_mutation(mutation)["errors"])

    def test_fitted_ignition_output_is_rejected(self):
        def mutation(root):
            comp=root.find("components/comp[@ref='R128']")
            for item in list(comp.findall("property")):
                if item.get("name")=="dnp": comp.remove(item)
        self.assertTrue(self.check_mutation(mutation)["errors"])

    def test_incompatible_root_tvs_is_rejected(self):
        def mutation(root): root.find("components/comp[@ref='D502']/value").text="SMBJ33CA"
        self.assertTrue(self.check_mutation(mutation)["errors"])


if __name__=="__main__": unittest.main()
