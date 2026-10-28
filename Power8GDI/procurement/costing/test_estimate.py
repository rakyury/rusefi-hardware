import copy
import unittest
from decimal import Decimal
from build_estimate import HERE, read, purchase, tier_price, group_selection, cost_bom, build_summary, load_catalog


class PurchasingTests(unittest.TestCase):
    def test_real_reel_moq_is_paid_in_full(self):
        p = purchase(3, {"tiers": [[800, .35583], [2400, .30773]], "minimum_order_quantity": 800, "order_multiple": 800, "stock_units": 820})
        self.assertEqual(p["purchase_qty"], 800)
        self.assertEqual(p["catalog_subtotal_usd"], 284.66)
        self.assertEqual(p["moq_rounding_qty"], 797)
        self.assertTrue(p["stock_covers_purchase"])

    def test_real_break_buy_up_reduces_cash_cost(self):
        p = purchase(9, {"tiers": [[1,3.05],[10,1.971],[50,1.5074]], "stock_units": 0})
        self.assertEqual(p["purchase_qty"], 10)
        self.assertEqual(p["buy_up_qty"], 1)
        self.assertEqual(p["catalog_subtotal_usd"], 19.71)
        self.assertFalse(p["stock_covers_purchase"])

    def test_exact_boundary_and_no_tier_extrapolation_below_moq(self):
        self.assertEqual(tier_price([[1,1.53],[10,1.2]], 10), (10,Decimal("1.2")))
        with self.assertRaises(ValueError):
            tier_price([[800,.35]], 2)

    def test_unreported_stock_is_unknown(self):
        self.assertIsNone(purchase(3, {"tiers": [[1,2]]})["stock_covers_purchase"])


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read(HERE / "selection_snapshot.json")
        cls.inputs = read(HERE / "estimate_inputs.json")
        cls.process = read(HERE / "process_evidence.json")
        cls.bom = cost_bom(cls.snapshot, cls.inputs, load_catalog())
        cls.summary = build_summary(cls.bom, cls.inputs, cls.process)

    def test_every_fitted_reference_costed_once(self):
        refs = [r for g in self.bom["groups"] for r in g["refs"]]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(len(refs), self.snapshot["counts"]["fitted_refs"])
        self.assertEqual(self.bom["coverage"]["catalog_priced_fitted_refs"] + self.bom["coverage"]["allowance_fitted_refs"], len(refs))

    def test_duplicate_mpn_contexts_combined_for_purchase(self):
        groups = self.bom["groups"]
        keys = [(g["manufacturer"], g["mpn"]) for g in groups if g["mpn"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_duplicate_reference_rejected(self):
        bad = copy.deepcopy(self.snapshot)
        bad["references"].append(bad["references"][0])
        with self.assertRaises(ValueError):
            group_selection(bad)

    def test_unknown_prices_never_turn_into_free_components(self):
        unknown = [g for g in self.bom["groups"] if not g["price_offer"]]
        self.assertTrue(unknown)
        for g in unknown:
            for b in g["batches"].values():
                self.assertIsNone(b["unit_price_usd"])
                self.assertIsNone(b["catalog_subtotal_usd"])
                self.assertGreater(b["allowance_base_usd"], 0)

    def test_quantities_and_paid_inventory_reconcile(self):
        for g in self.bom["groups"]:
            for n, b in g["batches"].items():
                self.assertEqual(b["fitted_qty"], int(n) * g["quantity_per_board"])
                self.assertGreaterEqual(b["purchase_qty"], b["fitted_qty"] + b["attrition_qty"])
                self.assertEqual(b["purchase_qty"] - b["fitted_qty"], b["unused_inventory_before_attrition_qty"])

    def test_minimum_blank_order_explicit_and_setup_not_per_board(self):
        one, ten = self.summary["batches"]
        self.assertEqual((one["fabricated_boards"], one["unused_blanks"]), (5,4))
        self.assertEqual((ten["fabricated_boards"], ten["unused_blanks"]), (10,0))
        one_items = {i["id"]: i for i in one["line_items"]}
        ten_items = {i["id"]: i for i in ten["line_items"]}
        self.assertEqual(one_items["assembly_setup"]["base_usd"], ten_items["assembly_setup"]["base_usd"])
        self.assertEqual(one_items["pcb"]["base_usd"], 140.32)
        self.assertEqual(ten_items["pcb"]["base_usd"], 186)

    def test_solder_joints_not_placements(self):
        one = self.summary["batches"][0]
        self.assertEqual(one["smt_solder_lands"], 3210)
        self.assertNotEqual(one["smt_solder_lands"], one["smt_placements"])
        self.assertEqual(one["tht_solder_lands"], 162)

    def test_totals_and_ranges_reconcile(self):
        for b in self.summary["batches"]:
            for label in ("low", "base", "high"):
                self.assertAlmostEqual(b["totals"][f"{label}_usd"], sum(x[f"{label}_usd"] for x in b["line_items"]), places=2)
            for item in b["line_items"]:
                self.assertLessEqual(item["low_usd"], item["base_usd"])
                self.assertLessEqual(item["base_usd"], item["high_usd"])
            self.assertFalse(b["cost_is_complete_factory_quote"])


if __name__ == "__main__":
    unittest.main()
