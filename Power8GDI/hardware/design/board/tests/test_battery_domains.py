"""Verify classification follows power pins and refuses stale pin maps."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from audit_battery_voltage_domains import discover


class BatteryDomainTests(unittest.TestCase):
    def edited(self,change):
        root=ET.parse(HERE.parent/'core.net');change(root)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'changed.xml';root.write(p);return discover(p)

    def test_renamed_motor_power_net_keeps_domain(self):
        def edit(root):root.find("nets/net[@name='MOTOR3_MOTOR_A']").set('name','renamed_output_without_voltage_hint')
        domains=self.edited(edit)
        self.assertIn('renamed_output_without_voltage_hint',domains)
        self.assertNotIn('MOTOR3_DIR_FILTERED',domains)
        self.assertNotIn('+3V3',domains)

    def test_wrong_pin_function_is_rejected(self):
        def edit(root):root.find("nets/net/node[@ref='U6200'][@pin='11']").set('pinfunction','GND')
        with self.assertRaisesRegex(ValueError,'expected CAP'):self.edited(edit)

    def test_connected_floating_exposed_pad_is_rejected(self):
        def edit(root):
            net=root.find("nets/net[@name='unconnected-(U6200-EP_FLOAT-Pad13)']")
            ET.SubElement(net,'node',{'ref':'TEST_PAD','pin':'1'})
        with self.assertRaisesRegex(ValueError,'must remain electrically floating'):self.edited(edit)
