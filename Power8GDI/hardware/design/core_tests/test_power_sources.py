"""Power flags must not conceal a removed/DNP/disconnected physical path."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from power_sources import HERE,verify


class PowerSourceTests(unittest.TestCase):
    def test_real_sources(self):self.assertEqual(verify()['errors'],[])

    def mutated(self,edit):
        root=ET.parse(HERE/'core.net');edit(root)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'broken.net';root.write(path);return verify(path)['errors']

    def test_unpopulated_analog_supply_filter_rejected(self):
        def change(root):ET.SubElement(root.find('components/comp[@ref="R101"]'),'property',name='dnp')
        self.assertTrue(self.mutated(change))

    def test_disconnected_buck_output_rejected(self):
        def change(root):
            n=root.find('nets/net[@name="+5V_CORE"]');n.remove(n.find('node[@ref="L5200"][@pin="2"]'))
        self.assertTrue(self.mutated(change))

    def test_removed_gdi_boost_rectifier_rejected(self):
        def change(root):
            n=root.find('components');n.remove(n.find('comp[@ref="D212"]'))
        self.assertTrue(self.mutated(change))

    def test_missing_external_motor_feed_rejected(self):
        def change(root):
            n=root.find('nets/net[@name="VBAT_EWG_FUSED"]');n.remove(n.find('node[@ref="J601"][@pin="34"]'))
        self.assertTrue(self.mutated(change))
