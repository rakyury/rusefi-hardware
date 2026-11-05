import csv
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PinoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "pinout/power8gdi_revA_pinout.csv").open(
            encoding="utf-8", newline=""
        ) as file:
            cls.rows = list(csv.DictReader(file))

    def test_136_connections(self):
        self.assertEqual(136, len(self.rows))

    def test_four_connectors_numbered(self):
        for name in "ABCD":
            self.assertEqual(
                [f"{name}{i:02d}" for i in range(1, 35)],
                [r["pin"] for r in self.rows if r["connector"] == name],
            )

    def test_unique_net_names(self):
        self.assertEqual(136, len({row["net"] for row in self.rows}))

    def test_required_channels(self):
        nets = {row["net"] for row in self.rows}
        for i in range(1, 7):
            for name in (f"DI{i}_HIGH", f"DI{i}_LOW", f"IGN{i}"):
                self.assertIn(name, nets)
        for i in range(1,9): self.assertIn(f"AUX_PWM{i}", nets)
        for i in (1, 2):
            for name in (f"HPFP{i}_HIGH", f"HPFP{i}_LOW"):
                self.assertIn(name, nets)
        for name in (
            "DBW_MOTOR_A", "DBW_MOTOR_B", "EWG_MOTOR_A", "EWG_MOTOR_B",
            "LIN1_BUS", "CAN1_H", "CAN1_L", "KNOCK1_SIG", "KNOCK2_SIG",
        ):
            self.assertIn(name, nets)

    def test_no_unassigned_nets(self):
        self.assertTrue(all(row["net"].strip() for row in self.rows))


if __name__ == "__main__":
    unittest.main()
