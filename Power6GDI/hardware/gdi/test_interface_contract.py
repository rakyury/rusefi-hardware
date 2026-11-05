import copy
import json
import subprocess
import sys
import unittest

from validate_interface_contract import CONTRACT, validate


class InterfaceContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def invalid(self, expected):
        errors = validate(self.contract)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_baseline_and_source_hashes(self):
        self.assertEqual(validate(self.contract), [])

    def test_shared_control_nets(self):
        for role in ("DRVEN", "RESETB", "SPI_CSB", "FLAG0", "HPFP_CMD", "INJ1"):
            with self.subTest(role=role):
                changed = copy.deepcopy(self.contract)
                changed["stages"][1]["signals"][role]["logical_net"] = changed["stages"][0]["signals"][role]["logical_net"]
                self.assertTrue(any("shared or missing logical net" in e for e in validate(changed)))

    def test_shared_physical_pin_despite_different_net_names(self):
        for stage in self.contract["stages"]:
            stage["signals"]["DRVEN"].update(mcu_pin="PB4", mapping_status="PROPOSED")
        self.invalid("shared MCU pin")

    def test_pin_alias_not_accepted(self):
        self.contract["stages"][0]["signals"]["DRVEN"].update(mcu_pin="H144_LS_7", mapping_status="PROPOSED")
        self.invalid("canonical MCU pad")

    def test_enable_and_reset_cannot_alias_within_stage(self):
        signals = self.contract["stages"][0]["signals"]
        signals["RESETB"]["logical_net"] = signals["DRVEN"]["logical_net"]
        self.invalid("shared or missing logical net")

    def test_shared_enable_policy(self):
        self.contract["policy"]["shared_enable_allowed"] = True
        self.invalid("shared enables forbidden")

    def test_shared_disable_domain(self):
        self.contract["stages"][1]["disable_domain"] = self.contract["stages"][0]["disable_domain"]
        self.invalid("shared or missing disable domain")

    def test_controls_cannot_hide_in_shared_bus(self):
        self.contract["policy"]["shared_spi_wires"].append("DRVEN")
        self.invalid("only SPI data/clock")

    def test_can_timed_commands_rejected(self):
        self.contract["policy"]["engine_commands_over_can_allowed"] = True
        self.invalid("engine commands over CAN forbidden")

    def test_missing_source_digest(self):
        del self.contract["sources"]["gdi_driver"]["sha256_lf"]
        self.invalid("invalid sha256_lf")

    def test_missing_bom_provenance(self):
        del self.contract["sources"]["gdi_bom_d"]
        self.invalid("incomplete source manifest")

    def test_changed_source_digest(self):
        self.contract["sources"]["gdi_driver"]["sha256_lf"] = "0" * 64
        self.invalid("source digest changed")

    def test_missing_license_status(self):
        del self.contract["sources"]["gdi_schematic"]["license_status"]
        self.invalid("license status required")

    def test_missing_evidence(self):
        self.contract["stages"][1]["signals"]["DRVEN"]["evidence"] = []
        self.invalid("evidence required")

    def test_unknown_source(self):
        self.contract["signal_definitions"]["FLAG0"]["evidence"][0]["source"] = "made_up"
        self.invalid("unknown evidence source")

    def test_device_pin_drift(self):
        self.contract["signal_definitions"]["SPI_CSB"]["device_pin"] = 12
        self.invalid("unreviewed device pin")

    def test_hp_fp_mapping_cannot_be_promoted_without_review(self):
        self.contract["signal_definitions"]["HPFP_CMD"]["assignment_status"] = "VERIFIED_DEVICE_PIN"
        self.invalid("assignment status unsupported")

    def test_guessed_polarity(self):
        self.contract["signal_definitions"]["RESETB"]["active_level"] = "LOW"
        self.invalid("evidence required")

    def test_firmware_level_is_not_manufacturer_polarity_evidence(self):
        signal = self.contract["signal_definitions"]["RESETB"]
        signal.update(active_level="LOW", polarity_evidence=[{"source": "gdi_main", "locator": "initPt2001Interface"}])
        self.invalid("device polarity requires manufacturer evidence")

    def test_incomplete_interface(self):
        del self.contract["stages"][1]["signals"]["HPFP_CMD"]
        self.invalid("missing or unknown interface")

    def test_unknown_requires_followup(self):
        self.contract["signal_definitions"]["HPFP_CMD"]["evidence_required"] = ""
        self.invalid("unknown requires explicit follow-up")

    def test_no_hardware_ready_claim(self):
        self.contract["hardware_ready"] = True
        self.invalid("audit cannot claim hardware readiness")

    def test_known_bom_mismatch_cannot_be_erased(self):
        self.contract["reference"]["bom_consistency"] = "MATCH"
        self.invalid("recorded BOM mismatch")

    def test_structural_and_readiness_cli_exit_codes(self):
        command = [sys.executable, str(CONTRACT.with_name("validate_interface_contract.py"))]
        structural = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(structural.returncode, 0, structural.stderr)
        release = subprocess.run(command + ["--require-ready"], capture_output=True, text=True, timeout=30)
        self.assertEqual(release.returncode, 2, release.stderr)
        self.assertIn("Hardware readiness: BLOCKED", release.stdout)


if __name__ == "__main__":
    unittest.main()
