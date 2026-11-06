#!/usr/bin/env python3
"""Verify pinned RacingDash sources, compile them as C, test ECU C++ admission."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX"))
    parser.add_argument("--cc", default=os.environ.get("CC"))
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    cxx = args.cxx or shutil.which("clang++") or shutil.which("g++")
    cc = args.cc or shutil.which("clang") or shutil.which("gcc")
    if not cxx or not cc:
        parser.error("C11 and C++17 compilers required; use --cc/--cxx")
    if args.sanitizers and os.name == "nt":
        parser.error("--sanitizers requires a Linux/macOS UBSan toolchain")
    sanitize = ["-fsanitize=undefined", "-fno-sanitize-recover=all"] if args.sanitizers else []
    firmware = Path(__file__).resolve().parents[1]
    vendor = firmware / "vendor/racing_dash"
    manifest = json.loads((vendor / "PROVENANCE.json").read_text(encoding="utf8"))
    for name, metadata in manifest["files"].items():
        data = (vendor / name).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != metadata["sha256_lf"]:
            raise SystemExit("Pinned source hash mismatch: " + name)
    vectors = json.loads((firmware / "tests/data/racing_dash_expr_vectors.json").read_text(encoding="utf8"))
    if vectors["source_commit"] != manifest["commit"]:
        raise SystemExit("Compiler/runtime source revisions differ")
    subprocess.run([cxx, "--version"], check=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix="gdi6-racingdash-") as temp:
        build = Path(temp)
        rows = ["struct Fixture { unsigned char code[128]; unsigned short length; int a,b,expected; };",
                "static const Fixture fixtures[] = {"]
        for v in vectors["vectors"]:
            code = bytes.fromhex(v["bytecode_hex"])
            if len(code) > 128:
                raise SystemExit("Fixture too long")
            rows.append("{{" + ",".join(str(b) for b in code) + "}," +
                        ",".join(str(x) for x in (len(code), *v["input"], v["expected"])) + "},")
        rows.append("};")
        (build / "racing_dash_vectors.h").write_text("\n".join(rows) + "\n", encoding="utf8")
        objects = []
        for module, name in (("vm", "vm"), ("channel_engine", "channel"), ("can_tx", "can_tx")):
            obj = build / (name + ".o")
            subprocess.run([cc, "-std=c11", "-O2", *sanitize, "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", "-D_CRT_SECURE_NO_WARNINGS", "-UNDEBUG", "-c",
                            str(vendor / "shared" / module / (name + ".c")), "-o", str(obj)],
                           check=True, timeout=120)
            objects.append(str(obj))
        exe = build / ("racingdash.exe" if os.name == "nt" else "racingdash")
        subprocess.run([cxx, "-std=c++17", "-O2", *sanitize, "-Wall", "-Wextra", "-Werror", "-pedantic",
                        "-UNDEBUG", "-I", str(build), str(firmware / "runtime/racing_dash_guard.cpp"),
                        str(firmware / "tests/test_racing_dash_guard.cpp"), *objects, "-o", str(exe)],
                       check=True, timeout=120)
        subprocess.run([str(exe)], check=True, timeout=30)
    print("Pinned source hashes, 10 compiler vectors and native C VM/CAN regression: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
