"""Contract regressions and ideal event model, NOT analogue/coil simulation."""
import unittest
from build_ignition import make_ignition, calculations
from build_core_schematic import load_symbols
from core_schlib import uid


class IdealChannel:
    """Rising-edge non-retriggerable monostable plus latched comparator contract.

    No delay, analogue brownout, inductive behavior or energy model is implied.
    Supply-valid is an external qualification input, not an implemented supervisor.
    """
    def __init__(self):
        self.until=0.0
        self.previous=False
        self.oc=False

    def step(self,t,command,armed=True,overcurrent=False,logic_valid=True,driver_valid=True):
        self.oc |= overcurrent
        if command and not self.previous and t>=self.until:
            self.until=t+calculations()["window_nominal_ms"]
        self.previous=command
        return bool(command and t<self.until and armed and not self.oc and logic_valid and driver_valid)


class IgnitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sheets=make_ignition(load_symbols(),uid("Power8GDI_Core"))
        cls.parts={p["ref"]:p for s in cls.sheets for p in s.parts}

    def test_normal_dwell_finishes_on_command_fall(self):
        c=IdealChannel()
        self.assertTrue(c.step(1,True))
        self.assertFalse(c.step(4,False))
        self.assertTrue(c.step(20,True))

    def test_stuck_high_times_out_without_restarting(self):
        c=IdealChannel()
        self.assertTrue(c.step(0,True))
        for t in (13,20,1000): self.assertFalse(c.step(t,True))

    def test_retrigger_does_not_extend_window(self):
        c=IdealChannel()
        c.step(0,True)
        c.step(5,False)
        self.assertTrue(c.step(6,True))
        self.assertFalse(c.step(13,True))

    def test_retrigger_after_timeout_is_possible_and_not_claimed_latched(self):
        c=IdealChannel()
        c.step(0,True)
        c.step(13,False)
        self.assertTrue(c.step(14,True))

    def test_overcurrent_remains_latched_across_command_and_arm_changes(self):
        c=IdealChannel()
        c.step(0,True)
        self.assertFalse(c.step(1,True,overcurrent=True))
        c.step(5,False,armed=False)
        self.assertFalse(c.step(20,True))

    def test_unarmed_and_supply_invalid_inhibit_ideal_output(self):
        for kwargs in ({"armed":False},{"logic_valid":False},{"driver_valid":False}):
            self.assertFalse(IdealChannel().step(0,True,**kwargs))

    def test_bank_fault_is_physical_wired_bus_and_enable_path(self):
        for i in range(6):
            n=5420+i*20
            self.assertEqual(self.parts[f"U{n+2}"]["pins"]["5"],"IGN_OC_OK")
            self.assertEqual(self.parts[f"U{n+2}"]["pins"]["6"],"+3V3")
            self.assertEqual(self.parts[f"U{n+1}"]["pins"]["6"],"IGN_SAFE_EN")
        self.assertEqual(self.parts["U5400"]["pins"]["2"],"IGN_OC_OK")
        self.assertEqual(self.parts["U5401"]["pins"]["3"],"IGN_OC_OK_CLEAN")
        for ref in ("U5402","U5403","U5404"):
            self.assertEqual(self.parts[ref]["pins"]["1"],"IGN_SAFE_EN")
            self.assertEqual(self.parts[ref]["pins"]["8"],"IGN_SAFE_EN")

    def test_reference_range_and_no_duplicate_parts(self):
        self.assertEqual(sum(len(s.parts) for s in self.sheets),len(self.parts))
        self.assertTrue(all(5400<=int(ref[1:])<=5599 for ref in self.parts))

    def test_logic_variant_has_no_hv_devices_or_bypass_in_passive(self):
        other=make_ignition(load_symbols(),uid("Power8GDI_Core"),"logic")
        values=[p["value"] for s in other for p in s.parts]
        self.assertNotIn("STGB18N40LZT4",values)
        self.assertNotIn("INA300AQDGSRQ1",values)
        for ch in range(1,7):
            connected=[p for p in self.parts.values() if f"HARNESS_IGN{ch}" in p["pins"].values()]
            self.assertEqual(len(connected),1)
            self.assertTrue(connected[0]["ref"].startswith("Q"))
        with self.assertRaises(ValueError): make_ignition(load_symbols(),"bad","mixed")

    def test_threshold_and_timer_budget(self):
        c=calculations()
        self.assertAlmostEqual(c["trip_nominal_A"],9.93)
        self.assertLess(c["trip_threshold_budget_A"][0],9.93)
        self.assertGreater(c["trip_threshold_budget_A"][1],9.93)
        self.assertLess(c["window_component_budget_ms"][0],12.04224)
        self.assertGreater(c["window_component_budget_ms"][1],12.04224)
        self.assertFalse(c["dynamic_peak_current_bounded"])


if __name__=="__main__": unittest.main(verbosity=2)
