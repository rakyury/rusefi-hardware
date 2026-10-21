"""Verify resource tracker is honest, not a complete electrical design."""
import csv
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hardware'))
from resource_audit import (  # noqa: E402
    REQUIRED, ResourceConflict, audit, read_rows, validate_connector_groups,
)


class ResourceAuditContract(unittest.TestCase):
    def test_connector_budgets(self):
        validate_connector_groups()

    def test_required_signals_are_tracked(self):
        rows = read_rows()
        names = {row['function'] for row in rows}
        self.assertFalse(set(sum(REQUIRED.values(), [])) - names)

    def test_unresolved_still_block_release(self):
        r = audit(read_rows())
        self.assertFalse(r['complete'])
        self.assertGreater(len(r['unassigned_required']), 10)
        self.assertIn('PI1', r['unassigned_required'])
        self.assertIn('CAN2_RX', r['unassigned_required'])
        self.assertNotIn('SENT3', r['unassigned_required'])
        self.assertIn('AUX_PWM8', r['unassigned_required'])

    def test_mcu_collision_detected(self):
        rows = read_rows()
        rows[-1] = dict(rows[-1], stm32_pin=rows[0]['stm32_pin'])
        with self.assertRaisesRegex(ResourceConflict, 'overlaps'):
            audit(rows)

    def test_duplicate_function_detected(self):
        rows = read_rows()
        with self.assertRaisesRegex(ResourceConflict, 'Duplicate'):
            audit(rows + [dict(rows[0])])


if __name__ == '__main__':
    unittest.main()
