"""Apply the reviewed GDI8/four-motor resource revision without guessing pins."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def main():
    path=HERE/'mcu_gpio_draft.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    removed={'DIN5','DIN6','DIN7','DIN8','WBO1_CS_N','WBO2_CS_N','WBO_ADC_CS_N'}
    rows=[r for r in rows if r['function'] not in removed]
    revised={
      'HPFP1':('PD8','GPIO_TIMED','Dedicated scheduled pump command; moved offPC9 to reserve TIM3_CH4'),
      'DBW_DIR':('PI2','GPIO','Direction GPIO moved offPC7 to reserve TIM3_CH2'),
      'MOTOR3_PWM':('PC7','TIM3_CH2','DS11532 Table11 p78/AF2; same PWM frequency as other motor bridges'),
      'MOTOR3_DIR':('PI3','GPIO','Reserve motor direction; default low'),
      'MOTOR3_DISABLE':('PI10','GPIO','Reserve motor disable; external default high'),
      'MOTOR4_PWM':('PC9','TIM3_CH4','DS11532 Table11 p78/AF2; same PWM frequency as other motor bridges'),
      'MOTOR4_DIR':('PI4','GPIO','Reserve motor direction; default low'),
      'MOTOR4_DISABLE':('PI11','GPIO','Reserve motor disable; external default high'),
      'MOTOR_CS_N':('PB4','GPIO','Four TLE9201 diagnostics daisy-chain CS; external pullup and isolated MISO'),
      'WBO1_HEATER_PWM':('PA10','GPIO','Main-MCU heater permission, default low; local F042 supplies actual PWM'),
      'WBO2_HEATER_PWM':('PB2','GPIO','Main-MCU heater permission, default low; local F042 supplies actual PWM'),
    }
    by_name={r['function']:r for r in rows}
    for name,(pin,mode,note) in revised.items():
        row={'function':name,'stm32_pin':pin,'mcu_resource':mode,'status':'proposed','notes':note}
        if name in by_name:by_name[name].update(row)
        else:rows.append(row)
    pins=[r['stm32_pin'] for r in rows if r['stm32_pin']!='UNASSIGNED']
    assert len(pins)==len(set(pins)), 'Pin collision in explicit scope migration'
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['function','stm32_pin','mcu_resource','status','notes'])
        writer.writeheader();writer.writerows(rows)
    contract_path=HERE/'resource_contract.json'
    contract=json.loads(contract_path.read_text())
    contract['named_requirements']=[n for n in contract['named_requirements'] if n not in removed]
    for name in revised:
        if name not in contract['named_requirements'] and name!='HPFP1':contract['named_requirements'].append(name)
    contract['decisions']['motor_pwm_timebase']='TIM3_CH1_to_CH4_shared_frequency'
    # Old source observations are retained, but withdrawn functions are no longer active allocations.
    for group,items in list(contract['candidate_pin_evidence'].items()):
        if isinstance(items,dict):
            for name in removed:items.pop(name,None)
        elif isinstance(items,list):
            contract['candidate_pin_evidence'][group]=[x for x in items if not isinstance(x,dict) or x.get('function') not in removed]
    contract['candidate_pin_evidence']['four_motor_revision']={
        name:{'port':pin,'mode':mode,'note':note} for name,(pin,mode,note) in revised.items()}
    contract['sources']['DS11532']['locators'].append('Table11 p78 and Table13 PortC: PC6..PC9 AF2 TIM3_CH1..4') if 'Table11 p78 and Table13 PortC: PC6..PC9 AF2 TIM3_CH1..4' not in contract['sources']['DS11532']['locators'] else None
    contract_path.write_text(json.dumps(contract,indent=2)+'\n')
    path=ROOT/'pinout/power8gdi_revA_pinout.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    for row in rows:
        if row['net'] in {'DIN5','DIN6','DIN7','DIN8'}:
            row['net']={'DIN5':'MOTOR3_MOTOR_A','DIN6':'MOTOR3_MOTOR_B','DIN7':'MOTOR4_MOTOR_A','DIN8':'MOTOR4_MOTOR_B'}[row['net']]
            row['group']='H-Bridge' if 'group' in row else row.get('group','')
            # Preserve the actual source CSV schema (some revisions use category).
            if 'category' in row:row['category']='H-Bridge'
            row['notes']='Reserved H-bridge motor terminal; previous DIN allocation superseded2026-10-23'
        if row['net'].startswith('IGN'):
            row['notes']='Passive B58 coil primary low-side; logic-coil assembly alternative must be mutually exclusive'
    fields=list(csv.DictReader(path.open(encoding='utf-8-sig')).fieldnames)
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(f'Applied Huge GDI8 profile: {len(pins)} unique GPIO allocations; 4 motor terminal pairs')

if __name__=='__main__':main()
