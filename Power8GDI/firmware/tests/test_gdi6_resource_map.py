"""Mutation tests for the hardware-to-software scheduling resource boundary."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "dual_gdi/generate_resource_map.py"
spec = importlib.util.spec_from_file_location("resource_map", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResourceMapTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(module.SOURCE.read_text(encoding="utf-8"))

    def rendered(self, data):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "contract.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            return module.render(source)

    def test_committed_header_matches_current_contract(self):
        self.assertEqual(module.render(module.SOURCE), module.OUTPUT.read_text(encoding="utf-8"))

    def test_missing_duplicate_and_invalid_channels_are_rejected(self):
        for channels in ([1], [1, 1], [1, 7], [1, True]):
            data = copy.deepcopy(self.contract)
            data["shared_current_paths"][0]["channels"] = channels
            with self.subTest(channels=channels), self.assertRaises(ValueError):
                self.rendered(data)

    def test_new_concurrency_or_missing_phase_requires_implementation_review(self):
        for key in ("shared_current_paths", "boost_supplies"):
            data = copy.deepcopy(self.contract)
            maximum = "max_simultaneously_active" if key == "shared_current_paths" else "max_simultaneous_boost_phases"
            data[key][0][maximum] = 2
            with self.assertRaises(ValueError):
                self.rendered(data)
        data = copy.deepcopy(self.contract)
        data["phases_owning_shared_current_path"].remove("demagnetization")
        with self.assertRaises(ValueError):
            self.rendered(data)

    def test_bad_or_implicit_qualification_is_rejected(self):
        for key, value in (("qualified_demagnetization_guard_us", 0),
                           ("qualified_demagnetization_guard_us", True),
                           ("qualified_demagnetization_guard_us", -1),
                           ("qualified_demagnetization_guard_us", 2**32),
                           ("engine_permission", 1),
                           ("deny_when_guard_is_unqualified", False)):
            data = copy.deepcopy(self.contract)
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.rendered(data)


if __name__ == "__main__":
    unittest.main()
