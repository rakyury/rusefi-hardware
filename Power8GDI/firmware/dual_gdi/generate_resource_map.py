"""Generate reviewed channel resources; never infer qualified timing from geometry."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "hardware/design/gdi/scheduling_contract.json"
OUTPUT = HERE / "gdi6_resource_map.h"


def render(source):
    raw = Path(source).read_bytes().replace(b"\r\n", b"\n")
    data = json.loads(raw)
    if data["schema_version"] != 1 or data["profile"] != "sport-gdi6":
        raise ValueError("Unsupported scheduling contract")
    paths, boosts = [-1] * 6, [-1] * 6
    for key, target, maximum in (("shared_current_paths", paths, "max_simultaneously_active"),
                                 ("boost_supplies", boosts, "max_simultaneous_boost_phases")):
        for index, group in enumerate(data[key]):
            if group[maximum] != 1:
                raise ValueError("Admission supports exclusive resources only")
            for channel in group["channels"]:
                if type(channel) is not int or channel not in range(1, 7) or target[channel-1] != -1:
                    raise ValueError("Duplicate or invalid channel")
                target[channel-1] = index
        if -1 in target:
            raise ValueError("Every DI channel must have a resource")
    if set(data["phases_owning_shared_current_path"]) != {"boost", "pickup", "hold", "demagnetization"}:
        raise ValueError("All current phases must own the resource")
    if data["deny_when_guard_is_unqualified"] is not True:
        raise ValueError("Unqualified guard must fail closed")
    guard = data["qualified_demagnetization_guard_us"]
    if guard is not None and (type(guard) is not int or guard <= 0 or guard >= 2**32):
        raise ValueError("Invalid qualified guard")
    if type(data["engine_permission"]) is not bool:
        raise ValueError("Engine permission must be explicit")
    return ("// Generated from hardware/design/gdi/scheduling_contract.json. Do not edit.\n"
            f"// Normalized SHA256: {hashlib.sha256(raw).hexdigest()}\n"
            "#pragma once\n#include <array>\n#include <cstdint>\nnamespace power6gdi {\n"
            f"inline constexpr std::array<std::uint8_t, 6> CurrentPath = {{{', '.join(map(str, paths))}}};\n"
            f"inline constexpr std::array<std::uint8_t, 6> BoostSupply = {{{', '.join(map(str, boosts))}}};\n"
            f"inline constexpr bool ContractEnginePermission = {str(data['engine_permission']).lower()};\n"
            f"inline constexpr bool ContractGuardQualified = {str(guard is not None).lower()};\n"
            f"inline constexpr std::uint32_t ContractGuardUs = {guard or 0};\n"
            "} // namespace power6gdi\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render(args.source)
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit("Resource header is stale; regenerate after contract review")
    else:
        OUTPUT.write_text(text, encoding="utf-8", newline="\n")
