"""Block classification used by the autoroute review (pcbnew import only)."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import layout_profile
import review_autoroute as r

HV={'PTA_VBOOST','Net-(U201-B_HS1)','Net-(Q203-S)'}


class ReviewAutorouteTests(unittest.TestCase):
    def test_blocks(self):
        cases={'GND':'gnd','HARNESS_SENSOR_GND_B':'gnd','HARNESS_IGN3':'ignition_hv','VBAT_GDI_A_FUSED':'battery','PTA_+Batt_filtered':'battery','PTA_VBOOST':'gdi_hv','Net-(Q203-S)':'gdi_hv',
               '+3V3':'logic_supply','+5V_CORE':'logic_supply','LP5_FB':'logic_supply','PTB_VCC1P5':'logic_supply','LP5_SW':'switching_supply','LP33_SW':'switching_supply',
               'CAN1_H':'comms','USB_DM':'comms','WBO1_CAN_TX':'comms','ADC_CLT':'analog_sensor','CLT_DIV':'analog_sensor','KNOCK1_AC':'analog_sensor',
               'WBO1_Un_sense':'analog_sensor','HALL2_FILTERED':'digital_sensor','HARNESS_CAM1':'digital_sensor','IGN2_GATE':'ignition_driver','IGN_SAFE_EN':'ignition_driver',
               'PTA_CLK':'gdi_control','GDI_SPI2_MISO':'gdi_control','Net-(U201-IRQ)':'gdi_control','DI4':'low_side_outputs','HPFP2':'low_side_outputs','LS3_CS_N':'low_side_outputs','LS_RESET_N':'low_side_outputs','HARNESS_PI3':'low_side_outputs','CRANK':'analog_sensor','HARNESS_KNOCK1_SIG':'analog_sensor',
               'EWG_MOTOR_B':'motor','MOTOR13_VS':'motor','WBO1_nRESET':'wbo','HARNESS_WBO1_CONTACT4':'wbo','NRST':'mcu_core','SD_CS':'mcu_core','MCU_VCAP_1':'mcu_core','Xyz':'other'}
        for net,block in cases.items():
            self.assertEqual(r.classify(net,HV),block,net)

    def test_every_router_touched_net_has_a_block(self):
        report=json.loads((HERE/'autoroute_190x206/autoroute_report.json').read_text())
        other=[n for n in report['nets_touched'] if r.classify(n,HV)=='other']
        self.assertEqual(other,[])

    def test_netclass_widths_honour_patterns(self):
        default,w=r.netclass_widths(HERE/'autoroute_190x206/Power8GDI_Review.kicad_pro')
        self.assertEqual((default,w.get('+3V3',default),w.get('+5V_CORE',default),w.get('VBAT_GDI_A',default),w.get('PTA_VBOOST',default),w.get('ADC_CLT',default)),(.25,.4,.4,.6,.8,.25))

    def test_areas_follow_profile(self):
        layout_profile.configure(HERE/'layout_profiles/190x206_donor.json')
        t=r.areas({'stage_A':(5,5,88,150),'stage_B':(97,4,180,149)})
        self.assertEqual(list(t)[:2],['stage_A','stage_B'])
        self.assertEqual(r.area_of((40,100),t),'stage_A');self.assertEqual(r.area_of((160,166),t),'mcu')
        self.assertEqual(r.area_of((100,200),t),'connector_strip');self.assertEqual(r.area_of((92,100),t),'elsewhere')
        layout_profile.configure()


if __name__=='__main__':
    unittest.main()
