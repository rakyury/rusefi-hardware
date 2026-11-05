"""Read-only freshness gates for saved estimates and integrated input artifacts.

The integrated input checks skip in an isolated costing checkout. Set
GDI6_COST_REQUIRE_INTEGRATED_INPUTS=1 in post-merge CI to forbid those skips.
No artifact is regenerated or rewritten by these tests.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from build_estimate import (
    HERE, PROJECT, build_summary, compact_selection, cost_bom, load_catalog,
    normalized_text_sha256, read,
)


class SavedArtifactFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read(HERE / "selection_snapshot.json")
        cls.inputs = read(HERE / "estimate_inputs.json")
        cls.process = read(HERE / "process_evidence.json")
        cls.recomputed_bom = cost_bom(cls.snapshot, cls.inputs, load_catalog())

    def test_saved_costed_bom_matches_recomputation(self):
        self.assertEqual(
            read(HERE / "costed_bom.json"), self.recomputed_bom,
            "costed_bom.json is stale: rerun build_estimate.py after reviewing input changes",
        )

    def test_saved_summary_matches_recomputation(self):
        self.assertEqual(
            read(HERE / "estimate_summary.json"),
            build_summary(self.recomputed_bom, self.inputs, self.process),
            "estimate_summary.json is stale: rerun build_estimate.py after reviewing input changes",
        )


class IntegratedInputFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = read(HERE / "selection_snapshot.json")
        cls.inputs = read(HERE / "estimate_inputs.json")

    def integrated_path(self, path):
        if path.is_file():
            return path
        message = f"Integrated input missing: {path.relative_to(PROJECT)}"
        if os.environ.get("GDI6_COST_REQUIRE_INTEGRATED_INPUTS") == "1":
            self.fail(message)
        self.skipTest(message + "; enable strict input checks after integration")

    def current_joints(self):
        return read(self.integrated_path(PROJECT / self.inputs["assembly"]["land_count_source"]))

    def test_frozen_selection_matches_current_selection(self):
        path = self.integrated_path(PROJECT / "procurement/selection/bom_selection.json")
        self.assertEqual(
            self.snapshot, compact_selection(path),
            "Costing snapshot is stale: rebuild with --selection procurement/selection/bom_selection.json",
        )

    def test_costing_inputs_match_current_land_report(self):
        joints = self.current_joints()
        cfg = self.inputs["assembly"]
        self.assertEqual(cfg["smt_solder_lands_per_board"], joints["smt_solder_lands"], "SMT land count changed")
        self.assertEqual(cfg["tht_solder_lands_per_board"], joints["tht_solder_lands"], "THT land count changed")
        self.assertEqual(self.snapshot["counts"]["fitted_refs"], joints["fitted_positions"], "Fitted count changed")
        self.assertEqual(cfg["land_count_board_sha256"], joints["board_sha256"], "Costing land provenance is stale")
        self.assertEqual(
            sorted(cfg["xray_candidate_refs"]), sorted(joints["hidden_pad_xray_candidates"]),
            "Hidden-pad package selection changed",
        )
        self.assertEqual(cfg["xray_packages_per_board"], len(joints["hidden_pad_xray_candidates"]))
        if "records" in joints:
            self.assertEqual(sum(r["smt_solder_lands"] for r in joints["records"]), joints["smt_solder_lands"])
            self.assertEqual(sum(r["tht_solder_lands"] for r in joints["records"]), joints["tht_solder_lands"])

    def test_land_report_hash_matches_current_board(self):
        joints = self.current_joints()
        assembly_path = PROJECT / self.inputs["assembly"]["land_count_source"]
        board = assembly_path.parent / "Power8GDI_Review.kicad_pcb"
        # If the report exists, a missing PCB is an error even in the optional
        # input mode: otherwise a detached report could masquerade as current.
        self.assertTrue(board.is_file(), f"Land report exists without its PCB: {board}")
        actual_hash = normalized_text_sha256(board)
        self.assertEqual(joints["board_sha256"], actual_hash, "Regenerate assembly_joints.json from current PCB")
        self.assertEqual(self.inputs["assembly"]["land_count_board_sha256"], actual_hash, "Update costing land provenance after PCB review")


class CrossPlatformDigestTests(unittest.TestCase):
    def test_compact_selection_equal_for_lf_crlf_and_utf8_bom(self):
        source = {"generated_date": "2026-10-28", "counts": {"fitted_refs": 0},
                  "bom_snapshot": {}, "references": []}
        payload = (json.dumps(source, indent=2) + "\n").encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / "lf.json"
            crlf = Path(directory) / "crlf.json"
            bom = Path(directory) / "bom.json"
            lf.write_bytes(payload)
            crlf.write_bytes(payload.replace(b"\n", b"\r\n"))
            bom.write_bytes(b"\xef\xbb\xbf" + payload.replace(b"\n", b"\r\n"))
            self.assertEqual(compact_selection(lf), compact_selection(crlf))
            self.assertEqual(compact_selection(lf), compact_selection(bom))
            self.assertEqual(normalized_text_sha256(lf), normalized_text_sha256(crlf))
            # Normalization must not hide a substantive input change.
            crlf.write_bytes(payload.replace(b"2026-10-28", b"2026-10-29"))
            self.assertNotEqual(normalized_text_sha256(lf), normalized_text_sha256(crlf))


if __name__ == "__main__":
    unittest.main()
