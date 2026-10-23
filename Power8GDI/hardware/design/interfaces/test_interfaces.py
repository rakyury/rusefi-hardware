"""Fault mutations exercise source-derived pin/power invariants, not CAD formatting."""
from copy import deepcopy
import unittest
from check_interfaces import check,electrical_checks,read_netlists


class Interfaces(unittest.TestCase):
    def setUp(self):self.components,self.pins,_=read_netlists()
    def test_export_matches_manifest_and_package(self):self.assertEqual(check()['errors'],[])
    def assert_mutation_rejected(self,ref,pad,net):
        pins=dict(self.pins);pins[(ref,str(pad))]=net
        self.assertTrue(electrical_checks(self.components,pins))
    def test_usb_host_cannot_power_core(self):self.assert_mutation_rejected('J1501',1,'+5V_CORE')
    def test_usb_fet_drain_source_swap(self):self.assert_mutation_rejected('Q1510',3,'GND')
    def test_sd_switch_not_mixed_with_shell(self):self.assert_mutation_rejected('J1502',11,'SD_CD')
    def test_tracker_input_isolation_polarity(self):self.assert_mutation_rejected('D1530',1,'VBAT_LOGIC_PROTECTED')
    def test_tracker_fb_must_follow_own_output(self):self.assert_mutation_rejected('U1531',4,'SENSOR_5V_A')
    def test_tracker_exposed_pad_must_be_grounded(self):self.assert_mutation_rejected('U1530',9,'SENSOR_A_IN')
    def test_missing_lin_commander_pullup_rejected(self):
        c=deepcopy(self.components);c['R1507']['dnp']=True
        self.assertTrue(electrical_checks(c,self.pins))
    def test_lin_commander_reverse_diode_rejected(self):self.assert_mutation_rejected('D1502',1,'LIN2_BUS')
    def test_lin_commander_undersized_resistor_rejected(self):
        c=deepcopy(self.components);c['R1507']['footprint']='Resistor_SMD:R_0603_1608Metric'
        self.assertTrue(electrical_checks(c,self.pins))
    def test_input_clamp_polarity(self):self.assert_mutation_rejected('D1600',1,'+5V_CORE')
    def test_sensor_return_must_exist(self):self.assert_mutation_rejected('R1532',2,'SENSOR_5V_B')
    def test_release_remains_blocked(self):self.assertEqual(check()['release_status'],'BLOCKED')


if __name__=='__main__':unittest.main()
