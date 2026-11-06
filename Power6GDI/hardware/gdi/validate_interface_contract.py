#!/usr/bin/env python3
"""Validate the GDI audit contract; PASS does not grant hardware readiness."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

CONTRACT = Path(__file__).with_name("interface_contract.json")
ROOT = Path(__file__).resolve().parents[3]
DEVICE_PINS = {"SPI_CSB": 13, "RESETB": 3, "DRVEN": 2, "FLAG0": 10,
               "HPFP_CMD": None, "INJ1": 4, "INJ2": 5, "INJ3": 6, "INJ4": 7}


def validate(contract: dict, root: Path = ROOT, verify_sources: bool = True) -> list[str]:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    check(contract.get("schema") == "power8gdi.gdi-interface.v1", "unsupported schema")
    check(contract.get("status") == "AUDIT_ONLY", "this contract supports AUDIT_ONLY status")
    check(contract.get("hardware_ready") is False, "audit cannot claim hardware readiness")
    reference = contract.get("reference", {})
    check(reference.get("device") == "MC33PT2001AE" and reference.get("bom_device") == "MC33816"
          and reference.get("bom_consistency") == "MISMATCH", "recorded BOM mismatch must remain explicit")
    sources = contract.get("sources", {})
    check(isinstance(sources, dict) and bool(sources), "sources are required")
    if not isinstance(sources, dict):
        return errors
    check(set(sources) == {"gdi_schematic", "gdi_pcb", "gdi_bom_d", "gdi_main", "gdi_driver",
                           "gdi_features", "gdi_connector", "nxp_sds"}, "incomplete source manifest")
    for source_id, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f"{source_id}: malformed source")
            continue
        check(bool(source.get("revision")), f"{source_id}: revision required")
        check(bool(source.get("license_status")), f"{source_id}: license status required")
        check(urlparse(source.get("url", "")).scheme == "https", f"{source_id}: HTTPS source URL required")
        if source.get("kind") == "repository":
            for key, length in (("revision", 40), ("git_blob_sha1", 40), ("sha256_lf", 64)):
                check(bool(re.fullmatch(rf"[0-9a-f]{{{length}}}", source.get(key, ""))),
                      f"{source_id}: invalid {key}")
            path = (root / source.get("path", "")).resolve()
            inside_root = root.resolve() in path.parents
            check(inside_root, f"{source_id}: path outside repository")
            if verify_sources and inside_root:
                try:
                    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                    check(digest == source.get("sha256_lf"), f"{source_id}: source digest changed")
                except OSError as error:
                    errors.append(f"{source_id}: cannot verify source: {error}")
        elif source.get("kind") == "manufacturer":
            host = urlparse(source.get("url", "")).hostname or ""
            check(host == "nxp.com" or host.endswith(".nxp.com"), f"{source_id}: manufacturer host is not NXP")
            check(bool(re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", ""))),
                  f"{source_id}: document digest required")
        else:
            errors.append(f"{source_id}: unsupported provenance kind")

    def evidence(items, context: str, manufacturer_only: bool = False) -> None:
        check(isinstance(items, list) and bool(items), f"{context}: evidence required")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{context}: malformed evidence")
                continue
            check(item.get("source") in sources, f"{context}: unknown evidence source")
            check(bool(item.get("locator")), f"{context}: evidence locator required")
            if manufacturer_only:
                check(sources.get(item.get("source"), {}).get("kind") == "manufacturer",
                      f"{context}: device polarity requires manufacturer evidence")

    policy = contract.get("policy", {})
    check(policy.get("stage_count") == 2, "exactly two stages required")
    check(policy.get("independent_disable_domains") is True, "independent disable domains required")
    check(policy.get("shared_enable_allowed") is False, "shared enables forbidden")
    check(policy.get("engine_commands_over_can_allowed") is False, "engine commands over CAN forbidden")
    check(policy.get("shared_spi_wires") == ["SCLK", "MOSI", "MISO"], "only SPI data/clock may be shared")
    definitions = contract.get("signal_definitions", {})
    check(set(definitions) == set(DEVICE_PINS), "missing or unknown signal definitions")
    for role, definition in definitions.items():
        check(definition.get("device_pin") == DEVICE_PINS.get(role), f"{role}: unreviewed device pin")
        expected_status = ("UNKNOWN_MICROCODE_MAPPING" if role == "HPFP_CMD" else
                           "PROPOSED_START_ASSIGNMENT" if role.startswith("INJ") else "VERIFIED_DEVICE_PIN")
        check(definition.get("assignment_status") == expected_status, f"{role}: assignment status unsupported by audit")
        evidence(definition.get("evidence"), role)
        for level in ("active_level", "safe_boot_level"):
            check(definition.get(level) in ("UNKNOWN", "HIGH", "LOW", "HIGH_IMPEDANCE"),
                  f"{role}: invalid {level}")
            if definition.get(level) != "UNKNOWN":
                evidence(definition.get("polarity_evidence"), role, manufacturer_only=True)
        if "UNKNOWN" in (definition.get("active_level"), definition.get("safe_boot_level")):
            check(bool(definition.get("evidence_required")), f"{role}: unknown requires explicit follow-up")

    stages = contract.get("stages", [])
    check(len(stages) == 2 and {s.get("id") for s in stages} == {"A", "B"}, "stage identities must be A and B")
    nets: set[str] = set()
    pins: set[str] = set()
    domains: set[str] = set()
    for stage in stages:
        stage_id = stage.get("id")
        domain = stage.get("disable_domain")
        check(bool(domain) and domain not in domains, "shared or missing disable domain")
        domains.add(domain)
        check(stage.get("injector_count") == 4 and stage.get("pump_count") == 1,
              f"{stage_id}: requires four injectors and one pump")
        check(stage.get("device_variant") == "MC33PT2001AE", f"{stage_id}: unreviewed device variant")
        check(stage.get("selection_status") == "REFERENCE_ONLY", f"{stage_id}: selection not approved by this audit")
        signals = stage.get("signals", {})
        check(set(signals) == set(DEVICE_PINS), f"{stage_id}: missing or unknown interface")
        for role, signal in signals.items():
            net = signal.get("logical_net")
            check(isinstance(net, str) and bool(net) and net not in nets,
                  f"{stage_id}/{role}: shared or missing logical net")
            nets.add(net)
            evidence(signal.get("evidence"), f"{stage_id}/{role}")
            pin = signal.get("mcu_pin")
            if pin is None:
                check(signal.get("mapping_status") == "UNASSIGNED", f"{stage_id}/{role}: unknown pin must be UNASSIGNED")
            else:
                check(isinstance(pin, str) and bool(re.fullmatch(r"P[A-K](?:[0-9]|1[0-5])", pin)),
                      f"{stage_id}/{role}: use canonical MCU pad, not alias")
                check(pin not in pins, f"{stage_id}/{role}: shared MCU pin")
                pins.add(pin)
                check(signal.get("mapping_status") == "PROPOSED", f"{stage_id}/{role}: mapping approval outside audit")
    observations = contract.get("observed_reference_firmware", [])
    check(bool(observations), "reference findings required")
    for finding in observations:
        evidence(finding.get("evidence"), finding.get("id", "finding"))
    blockers = contract.get("blockers", [])
    check(bool(blockers), "audit must retain explicit blockers")
    check(all(item.get("id") and item.get("evidence_required") for item in blockers), "incomplete blocker")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--require-ready", action="store_true", help="fail release gate while audit remains blocked")
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        errors = validate(contract)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        print(f"GDI contract: FAIL: {error}", file=sys.stderr)
        return 1
    if errors:
        print("GDI contract: FAIL\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("GDI interface contract: PASS (audit consistency and local source hashes)")
    print(f"Hardware readiness: BLOCKED ({len(contract['blockers'])} recorded blockers; pins/polarities unresolved)")
    return 2 if args.require_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
