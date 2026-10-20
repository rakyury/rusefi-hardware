"""Reproduce offline checks from a clean checkout; never connect to an ECU.

Each subprocess has a separate log and an explicit outcome. Host tests do not
constitute an MCU build, electrical verification, or hardware qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("host", "cad", "all"), default="host")
    parser.add_argument("--output", type=Path, default=REPO / "build/power8gdi-checks")
    parser.add_argument("--cxx", help="GCC-compatible compiler executable (or set CXX)")
    parser.add_argument("--sanitizers", action="store_true", help="Enable UBSan on Linux/macOS")
    args = parser.parse_args(argv)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(ROOT / "configurator") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    results = []

    def record(name, command=None, cwd=ROOT, timeout=180, blocked=None):
        log = args.output / f"{name}.log"
        result = {"name": name, "command": command, "cwd": str(cwd), "log": log.name}
        if blocked:
            result.update(status="BLOCKED", reason=blocked)
            output = blocked + "\n"
        else:
            try:
                proc = subprocess.run(command, cwd=cwd, env=env, text=True,
                                      encoding="utf-8", errors="replace",
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      timeout=timeout, check=False)
                result.update(status="PASS" if proc.returncode == 0 else "FAIL",
                              returncode=proc.returncode)
                output = proc.stdout
            except (OSError, subprocess.TimeoutExpired) as exc:
                result.update(status="FAIL", reason=str(exc))
                output = str(exc) + "\n"
        log.write_text(output, encoding="utf-8")
        results.append(result)
        print(f"{name}: {result['status']} ({log})", flush=True)
        if result["status"] != "PASS":
            print(output[-4000:], flush=True)
        return result["status"] == "PASS"

    if args.suite in ("host", "all"):
        configured = args.cxx or os.environ.get("CXX")
        candidates = ("clang++", "g++", "c++") if os.name == "nt" else ("c++", "g++", "clang++")
        compiler = (shutil.which(configured) if configured else
                    next((p for c in candidates if (p := shutil.which(c))), None))
        if compiler:
            env["CXX"] = compiler
        compiler_error = None if compiler else "Install a C++17 compiler or set CXX to its executable."
        if args.sanitizers and os.name == "nt":
            compiler_error = "--sanitizers requires a Linux/macOS UBSan toolchain."
        flags = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-ffp-contract=off", "-UNDEBUG"]
        if args.sanitizers:
            flags += ["-fsanitize=undefined", "-fno-sanitize-recover=all"]
        sources = {
            "map4d": ["tests/test_map4d.cpp"],
            "map4d-blob": ["tests/test_map4d_blob.cpp"],
            "dual-hpfp": ["dual_hpfp/dual_hpfp_supervisor.cpp", "tests/test_dual_hpfp_supervisor.cpp"],
            "dual-hpfp-safety": ["dual_hpfp/dual_hpfp_supervisor.cpp", "tests/test_dual_hpfp_safety.cpp"],
        }
        with tempfile.TemporaryDirectory(prefix="power8gdi-host-") as build:
            for name, files in sources.items():
                if compiler_error:
                    record(f"cpp-{name}-build", blocked=compiler_error)
                    continue
                exe = Path(build) / (name + (".exe" if os.name == "nt" else ""))
                if record(f"cpp-{name}-build", [compiler, *flags, "-Iinclude", *files, "-o", str(exe)],
                          cwd=ROOT / "firmware"):
                    record(f"cpp-{name}", [str(exe)], cwd=ROOT / "firmware")
        if record("qt-runtime", [sys.executable, "-c", "from PyQt6.QtWidgets import QApplication; app=QApplication([])"]):
            if compiler_error:
                record("python-configurator", blocked="C++ compiler required for cross-language parity tests.")
            else:
                record("python-configurator", [sys.executable, "-m", "pytest", "tests", "-v"],
                       cwd=ROOT / "configurator")
        else:
            record("python-configurator", blocked="Qt runtime unavailable. Install configurator dependencies before testing.")
        record("static-interface", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        record("mcu-audit-contracts", [sys.executable, "-m", "unittest", "discover", "-s", "hardware/tests", "-v"])
        record("mcu-audit-structure", [sys.executable, "hardware/audit_resources.py", "--gate", "structure"])
        record("gdi-audit-contracts", [sys.executable, "-m", "unittest", "discover", "-s", "hardware/gdi", "-p", "test_*.py", "-v"])
        record("gdi-audit-structure", [sys.executable, "hardware/gdi/validate_interface_contract.py"])

    if args.suite in ("cad", "all"):
        cad_output = args.output / "cad-assets"
        env["POWER8GDI_CAD_OUTPUT"] = str(cad_output)
        if record("cad-runtime", [sys.executable, "-c", "import cadquery; print(cadquery.__version__)"]):
            if record("cad-generate", [sys.executable, str(ROOT / "mechanical/build_assembly.py"),
                                      "--output-dir", str(cad_output)], timeout=600):
                record("cad-contracts", [sys.executable, "-m", "unittest", "discover", "-s", "mechanical/tests", "-v"])
            else:
                record("cad-contracts", blocked="CAD generation failed; existing exports cannot count as current evidence.")
        else:
            record("cad-contracts", blocked="CadQuery unavailable. Install mechanical dependencies before testing.")

    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=REPO, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    passed = all(r["status"] == "PASS" for r in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "revision": revision, "working_tree_dirty": dirty,
        "suite": args.suite, "python": sys.version,
        "status": "PASS" if passed else "FAIL", "checks": results,
        "not_validated": ["Power8GDI MCU firmware build", "KiCad ERC/DRC", "vendor connector fit",
                          "physical fault injection", "thermal/EMC", "engine operation"],
    }
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Overall {args.suite}: {report['status']}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
