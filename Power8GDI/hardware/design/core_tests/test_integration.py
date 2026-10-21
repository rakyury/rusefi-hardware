import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('integration',HERE/'verify_integration.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class IntegrationTests(unittest.TestCase):
    def mutate(self,ref,pin,newnet):
        tree=ET.parse(HERE/'core.net');root=tree.getroot();found=None
        for net in root.findall('nets/net'):
            for n in list(net):
                if n.get('ref')==ref and n.get('pin')==str(pin):found=n;net.remove(n)
        self.assertIsNotNone(found)
        target=next(n for n in root.findall('nets/net') if n.get('name')==newnet);target.append(found)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mutant.xml';tree.write(path);return module.verify(path)
    def test_actual_export(self):self.assertEqual(module.verify(HERE/'core.net')['errors'],[])
    def test_ignition_bypass_rejected(self):self.assertTrue(self.mutate('U110',2,'IGN1')['errors'])
    def test_motor_permission_bypass_rejected(self):self.assertTrue(self.mutate('U910',1,'+3V3')['errors'])
    def test_wrong_vr_mode_rejected(self):self.assertTrue(self.mutate('U731',6,'+5V_CORE')['errors'])
    def test_mcu_harness_bypass_rejected(self):self.assertTrue(self.mutate('U101',40,'HARNESS_TPS1')['errors'])
    def test_connector_motor_swap_rejected(self):self.assertTrue(self.mutate('J604',1,'EWG_MOTOR_A')['errors'])

if __name__=='__main__':unittest.main()
