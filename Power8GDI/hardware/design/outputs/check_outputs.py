"""Independent physical-net checks and fault mutations for all24 TLE channels."""
from pathlib import Path
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
FUNCTIONS=[*[f'PI{i}' for i in range(1,9)],*[f'VVT{i}' for i in range(1,5)],*[f'AUX_PWM{i}' for i in range(1,9)],*[f'LS_AUX{i}' for i in range(1,5)]]

def verify(path):
    doc=ET.parse(path); pin={}; errors=[]
    for n in doc.findall('nets/net'):
        for e in n.findall('node'): pin[(e.get('ref'),e.get('pin'))]=n.get('name')
    values={c.get('ref'):c.findtext('value') for c in doc.findall('components/comp')}
    def expect(ref,p,n):
        if pin.get((ref,str(p)))!=n:errors.append(f'{ref}.{p} must be {n}, got {pin.get((ref,str(p)))}')
    for b in range(6):
        u=f'U{1101+b}';g=f'U{1121+b}'; base=1100+20*b
        if values.get(u)!='TLE9104SHXUMA1':errors.append('Wrong low-side variant '+u)
        for pad in [2,9,12,19,21]:expect(u,pad,'GND')
        for pad,n in [(15,'+3V3'),(16,'+5V_CORE'),(6,'LS_SPI_MOSI'),(8,'LS_SPI_SCK'),(5,f'LS{b+1}_SO'),(7,f'LS{b+1}_CS_N'),(13,'LS_RESET_N'),(14,f'LS{b+1}_ENABLE')]:expect(u,pad,n)
        expect(g,14,'+3V3');expect(g,7,'GND')
        for j,name in enumerate(FUNCTIONS[4*b:4*b+4]):
            expect(g,[1,3,5,9][j],name);expect(g,[2,4,6,8][j],name+'_INV')
            expect(u,[3,18,4,17][j],name+'_IN_N');expect(u,[1,20,10,11][j],'HARNESS_'+name)
            expect(f'R{base+3*j+1}',1,name);expect(f'R{base+3*j+1}',2,'GND')
            expect(f'R{base+3*j+2}',1,name+'_INV');expect(f'R{base+3*j+2}',2,name+'_IN_N')
            expect(f'R{base+3*j+3}',1,'+3V3');expect(f'R{base+3*j+3}',2,name+'_IN_N')
        expect(f'R{base+16}',1,'HW_ACTUATOR_ENABLE');expect(f'R{base+16}',2,f'LS{b+1}_ENABLE')
        expect(f'R{base+17}',1,f'LS{b+1}_ENABLE');expect(f'R{base+17}',2,'GND')
        expect(f'R{base+13}',1,f'LS_CS{b+1}');expect(f'R{base+14}',1,'+3V3')
    expect('U1140',2,'LS_RESET_RELEASE');expect('U1140',4,'LS_RESET_N')
    expect('R1242',1,'LS_RESET_N');expect('R1242',2,'GND')
    if values.get('R1242')!='1k 1%':errors.append('Reset pulldown must sink six internal100uA pullups')
    # Datasheet absolute timing vs typical is important: 15us is TYPICAL, not max.
    worst_reset_v=(6*100e-6+10e-6)*1000*1.01
    assert worst_reset_v<1
    e_limit=.007; vbat=16; clamp=50; current=1.4
    max_l=2*e_limit/current**2*(clamp-vbat)/clamp
    return {'status':'FAIL' if errors else 'PASS_STATIC_NETWORK','errors':errors,'output_channels':24,
            'shared_reset_pullup_worst_v':worst_reset_v,'candidate_max_inductance_mH_at_1p4A_16V_7mJ':max_l*1000,
            'six_driver_5V_supply_budget_mA':60,'full_load_thermal_rating_approved':False,
            'timing_15us':'typical only; no maximum injector timing guarantee','release_status':'BLOCKED'}

class Tests(unittest.TestCase):
    def test_actual(self):self.assertEqual(verify(ROOT/'core.net')['errors'],[])
    def mutant(self,ref,p,newnet):
        d=ET.parse(ROOT/'core.net');found=None
        for n in d.findall('nets/net'):
            for e in list(n):
                if e.get('ref')==ref and e.get('pin')==str(p):found=e;n.remove(e)
        self.assertIsNotNone(found)
        next(n for n in d.findall('nets/net') if n.get('name')==newnet).append(found)
        with tempfile.TemporaryDirectory() as f:
            path=Path(f)/'bad.xml';d.write(path);return verify(path)['errors']
    def test_kill_bypass(self):self.assertTrue(self.mutant('R1116',1,'+3V3'))
    def test_wrong_input_polarity_path(self):self.assertTrue(self.mutant('U1101',3,'PI1'))
    def test_output_swap(self):self.assertTrue(self.mutant('U1101',1,'HARNESS_PI2'))
    def test_missing_ep_ground(self):self.assertTrue(self.mutant('U1101',21,'+5V_CORE'))
    def test_reset_pullup_fault(self):self.assertTrue(self.mutant('R1242',2,'+3V3'))
    def test_every_bank_enable(self):
        for b in range(6):self.assertTrue(self.mutant(f'U{1101+b}',14,'+3V3'))

if __name__=='__main__':
    result=verify(ROOT/'core.net')
    (ROOT/'outputs/outputs_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    unittest.main()
