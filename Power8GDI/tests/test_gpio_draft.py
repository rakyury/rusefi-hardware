"""Static constraints only: AF, DMA, connector/current checks not complete."""
import csv
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GpioDraftContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / 'hardware/mcu_gpio_draft.csv').open(newline='') as f:
            cls.data = list(csv.DictReader(f))
        cls.pins = {item['function']: item['stm32_pin'] for item in cls.data}

    def test_names_unique(self):
        self.assertEqual(len(self.pins), len(self.data))

    def test_assigned_pins_have_no_collision(self):
        assigned = [row['stm32_pin'] for row in self.data if row['stm32_pin'] != 'UNASSIGNED']
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_gdi_resources(self):
        for prefix, n in [('DI', 8), ('IGN', 8), ('HPFP', 2)]:
            for i in range(1, n + 1):
                self.assertNotEqual('UNASSIGNED', self.pins[f'{prefix}{i}'])
        for prefix in ('PTA', 'PTB'):
            for suffix in ('CS', 'RESET', 'DRVEN', 'FLAG'):
                self.assertNotEqual('UNASSIGNED', self.pins[f'{prefix}_{suffix}'])

    def test_two_distinct_motor_bridges(self):
        for prefix in ('DBW', 'EWG'):
            for suffix in ('PWM', 'DIR', 'DISABLE'):
                self.assertNotEqual('UNASSIGNED', self.pins[f'{prefix}_{suffix}'])

    def test_unresolved_stay_explicit(self):
        for signal in ('LIN2_TX', 'LIN2_RX', 'CAN2_RX', 'CAN2_TX'):
            self.assertEqual('UNASSIGNED', self.pins[signal])

    def test_new_receiver_assignments_remain_proposed(self):
        expected={'SENT3':'PB6','SENT4':'PB7','CAM3':'PI5','CAM4':'PI6'}
        for row in self.data:
            if row['function'] in expected:
                self.assertEqual(row['stm32_pin'],expected[row['function']])
                self.assertEqual(row['status'],'proposed')

    def test_requirements_dont_fit_only_four_tle9104(self):
        # Eight PI + four VVT + eight general-purpose PWM + four service low-side.
        required_low_sides = 8 + 4 + 8 + 4
        self.assertEqual(required_low_sides, 24)
        self.assertGreater(required_low_sides, 4 * 4)
        self.assertEqual((required_low_sides + 3) // 4, 6)


if __name__ == '__main__':
    unittest.main()
