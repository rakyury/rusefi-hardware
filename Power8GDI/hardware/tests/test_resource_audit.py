import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HARDWARE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hardware_resource_audit', HARDWARE / 'audit_resources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.rows = module.read_csv(HARDWARE / 'mcu_gpio_draft.csv')
        self.connectors = module.read_csv(HARDWARE.parent / 'pinout/power8gdi_revA_pinout.csv')
        self.contract = json.loads((HARDWARE / 'resource_contract.json').read_text())

    def row(self, name):
        return next(row for row in self.rows if row['function'] == name)

    def report(self):
        return module.audit(self.rows, self.connectors, self.contract)

    def test_collision_free_draft_cannot_pass_qualification(self):
        report = self.report()
        self.assertEqual(report['structure_status'], 'pass')
        self.assertEqual(report['summary']['collision_findings'], 0)
        self.assertFalse(report['release_eligible'])
        self.assertTrue({'PI1', 'VVT4', 'AUX_PWM1', 'TPS1', 'FRP2', 'CAM4', 'HALL4'} <= set(report['missing_functions']))
        self.assertEqual(len(report['missing_functions']), 52)
        self.assertTrue({'SENT3', 'SENT4', 'CAN2_RX', 'LIN2_RX'} <= set(report['unassigned_functions']))
        self.assertEqual(report['verification']['DMA_routes'], 'unverified')

    def test_shared_peripheral_channel_collision_despite_unique_gpio(self):
        self.row('EWG_PWM')['mcu_resource'] = 'TIM3_CH1'
        findings = self.report()['findings']
        self.assertTrue(any(f['code'] == 'RESOURCE_COLLISION' and 'timer_channel TIM3_CH1' in f['detail'] for f in findings))

    def test_pin_collision(self):
        self.row('DI2')['stm32_pin'] = 'PG7'
        self.assertTrue(any(f['code'] == 'RESOURCE_COLLISION' and 'pin PG7' in f['detail'] for f in self.report()['findings']))

    def test_exti_port_alias_collision(self):
        self.row('PTB_FLAG')['stm32_pin'] = 'PA8'  # Different pin, same EXTI8 as PF8.
        findings = self.report()['findings']
        self.assertTrue(any(f['code'] == 'RESOURCE_COLLISION' and 'exti_line 8' in f['detail'] for f in findings))
        self.assertFalse(any('pin PA8' in f['detail'] for f in findings))

    def test_scheduler_timer_reservation(self):
        for resource in ('TIM5_CH1', 'TIM5_CAPTURE', 'TIM6'):
            self.row('DBW_PWM')['mcu_resource'] = resource
            self.assertTrue(any(f['code'] == 'RESERVED_TIMER' for f in self.report()['findings']))

    def test_storage_conflicts_are_conditional_until_selected(self):
        findings = self.report()['findings']
        matches = [f for f in findings if f['detail'].startswith('SDMMC1_4bit:')]
        self.assertEqual(matches[0]['category'], 'conditional_conflict')
        self.assertEqual(matches[0]['functions'], ['EWG_PWM', 'HPFP1'])
        self.contract['decisions']['storage_interface'] = 'SDMMC1_4bit'
        matches = [f for f in self.report()['findings'] if f['detail'].startswith('SDMMC1_4bit:')]
        self.assertEqual(matches[0]['category'], 'collision')

    def test_timer_timebase_and_pc13_require_review_without_false_collision(self):
        findings = self.report()['findings']
        self.assertTrue(any(f['code'] == 'SHARED_TIMER_TIMEBASE' and set(f['functions']) == {'DBW_PWM', 'EWG_PWM'} for f in findings))
        self.assertTrue(any(f['code'] == 'PC13_ELECTRICAL_REVIEW' and f['functions'] == ['IGN1'] for f in findings))

    def test_new_connector_function_cannot_disappear_from_requirements(self):
        self.connectors.append(dict(net='AUX_ANALOG3', group='Analog'))
        self.assertIn('AUX_ANALOG3', self.report()['missing_functions'])

    def test_bad_pin_status_duplicate_and_empty_inputs(self):
        for field, value in [('stm32_pin', 'PZ99'), ('status', 'verified')]:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.rows)
                changed[0][field] = value
                self.assertEqual(module.audit(changed, self.connectors, self.contract)['structure_status'], 'fail')
        self.rows.append(self.rows[0].copy())
        self.assertEqual(self.report()['structure_status'], 'fail')
        self.assertEqual(module.audit([], [], self.contract)['structure_status'], 'fail')

    def test_no_json_approval_shortcut(self):
        self.contract['release_eligible'] = True
        self.contract['target'].update(order_code='claimed', package='claimed', silicon_revision='claimed')
        self.contract['qualification_evidence_required'] = []
        self.assertFalse(self.report()['release_eligible'])
        self.contract['stage'] = 'qualified'
        self.assertEqual(self.report()['structure_status'], 'fail')

    def test_source_or_family_change_requires_new_review(self):
        self.contract['interface_pin_facts'][0]['source'] = 'missing-source'
        self.assertEqual(self.report()['structure_status'], 'fail')
        self.contract['target']['family'] = 'STM32H7'
        self.assertEqual(self.report()['structure_status'], 'fail')

    def test_cli_structure_is_distinct_from_default_release_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'audit.json'
            args = [sys.executable, str(HARDWARE / 'audit_resources.py'), '--output', str(output)]
            blocked = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            self.assertFalse(json.loads(output.read_text())['release_eligible'])
            structure = subprocess.run(args + ['--gate', 'structure'], capture_output=True, text=True)
            self.assertEqual(structure.returncode, 0, structure.stderr)
            self.assertEqual(json.loads(output.read_text()), json.loads((HARDWARE / 'resource_audit_report.json').read_text()))
            malformed = Path(directory) / 'bad.json'
            malformed.write_text('{invalid')
            bad = subprocess.run(args + ['--gate', 'structure', '--contract', str(malformed)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(json.loads(output.read_text())['structure_status'], 'fail')


if __name__ == '__main__':
    unittest.main()
