#!/usr/bin/env python3
"""Build/run GDI6 mass routing and explicit PT2001 profile host contracts."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX"))
    args = parser.parse_args()
    compiler = args.cxx or shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        parser.error("C++17 compiler missing; use --cxx")
    firmware = Path(__file__).resolve().parents[1]
    flags = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-ffp-contract=off", "-UNDEBUG", "-I", str(firmware / "dual_gdi")]
    sources = {
        "fuel-gdi6": ["fuel/allocation_gdi6.cpp", "tests/test_fuel_gdi6.cpp"],
        "pt2001-profiles": ["dual_gdi/dual_pt2001_safety.cpp", "tests/test_dual_pt2001_safety.cpp"],
    }
    subprocess.run([compiler, "--version"], check=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix="sport-gdi6-host-") as temporary:
        for name, paths in sources.items():
            executable = Path(temporary) / (name + (".exe" if os.name == "nt" else ""))
            subprocess.run([compiler, *flags, *(str(firmware / p) for p in paths),
                            "-o", str(executable)], check=True, timeout=120)
            subprocess.run([str(executable)], check=True, timeout=30)
            print(f"{name}: PASS", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
