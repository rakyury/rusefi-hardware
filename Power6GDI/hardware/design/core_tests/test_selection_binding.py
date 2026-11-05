import sys
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apply_selection import specifications

class SelectionBinding(unittest.TestCase):
    def setUp(self):
        self.row={'reference':'C5208','source_value':'47u 25V X7R','footprint':'Capacitor_SMD:C_1210_3225Metric',
          'ratings':{'capacitance_pf':47000000,'rated_voltage_v':25,'dielectric':'X7R'}}
    def test_nominal_match(self):self.assertEqual(specifications(self.row,self.row['source_value'],self.row['footprint']),[])
    def test_lower_voltage_and_dielectric_rejected(self):
        for key,bad in [('rated_voltage_v',10),('dielectric','X5R'),('capacitance_pf',4700000)]:
            row=deepcopy(self.row);row['ratings'][key]=bad
            self.assertTrue(specifications(row,row['source_value'],row['footprint']))
    def test_map_approval_cannot_change_circuit(self):
        self.row['approved_deviation']={'approved_by':'somebody'}
        self.assertTrue(specifications(self.row,'10u 25V X7R',self.row['footprint']))
        self.assertTrue(specifications(self.row,self.row['source_value'],'Capacitor_SMD:C_0603_1608Metric'))
    def test_explicit_mcu_deviation(self):
        row={'reference':'C114','source_value':'4.7u 16V X7R','footprint':'Capacitor_SMD:C_0603_1608Metric',
          'ratings':{'capacitance_pf':10000000,'rated_voltage_v':16,'dielectric':'X7R'}}
        self.assertEqual(specifications(row,'10u 16V X7R','Capacitor_SMD:C_1206_3216Metric'),[])
        self.assertTrue(specifications(row,'10u 16V X7R','Capacitor_SMD:C_0805_2012Metric'))

if __name__=='__main__':unittest.main()
