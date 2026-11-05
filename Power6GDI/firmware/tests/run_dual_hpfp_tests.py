#!/usr/bin/env python3
"""Compile/run the isolated HPFP host contracts on Windows, Linux or macOS."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX"),
                        help="C++17 compiler executable (or set CXX)")
    parser.add_argument("--sanitize", choices=("auto", "undefined", "none"), default="auto",
                        help="auto uses UBSan on non-Windows hosts")
    args = parser.parse_args()
    candidates = ("clang++", "g++") if os.name == "nt" else ("g++", "clang++")
    compiler = args.cxx or next((shutil.which(name) for name in candidates if shutil.which(name)), None)
    if not compiler:
        parser.error("C++17 compiler not found; use --cxx or set CXX")
    sanitize = args.sanitize
    if sanitize == "auto":
        sanitize = "none" if os.name == "nt" else "undefined"

    firmware = Path(__file__).resolve().parents[1]
    flags = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-UNDEBUG"]
    if sanitize == "undefined":
        flags.extend(["-fsanitize=undefined", "-fno-sanitize-recover=undefined"])
    print(f"HPFP host platform: {sys.platform}; sanitizer: {sanitize}", flush=True)

    def run(command: list[str], timeout: int) -> None:
        display = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
        print(f"$ {display}", flush=True)
        subprocess.run(command, check=True, timeout=timeout)

    try:
        run([compiler, "--version"], 30)
        with tempfile.TemporaryDirectory(prefix="power8gdi-hpfp-") as directory:
            for name in ("test_dual_hpfp_supervisor", "test_dual_hpfp_safety"):
                executable = Path(directory) / (name + (".exe" if os.name == "nt" else ""))
                run([compiler, *flags,
                     str(firmware / "dual_hpfp" / "dual_hpfp_supervisor.cpp"),
                     str(firmware / "tests" / f"{name}.cpp"), "-o", str(executable)], 120)
                run([str(executable)], 30)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"HPFP host suite: FAIL: {error}", file=sys.stderr)
        return 1
    print("HPFP host suite: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
