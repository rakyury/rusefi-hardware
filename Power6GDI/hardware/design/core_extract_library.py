"""One-time, source-pinned extraction from the installed official KiCad library."""
import copy
import hashlib
import json
from pathlib import Path
import sys

from core_schlib import Quoted, children, child, dump, parse

HERE = Path(__file__).resolve().parent
source_root = Path(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/kicad/symbols")
selected = [("MCU_ST_STM32F7", "STM32F767IITx", "STM32F767IIT6"),
            ("Device", "C", "C"), ("Device", "R", "R"),
            ("Device", "Crystal_GND24", "Crystal_GND24")]
libraries, records, output = {}, [], []
for library, original, name in selected:
    if library not in libraries:
        path = source_root / (library + ".kicad_sym")
        raw = path.read_bytes()
        libraries[library] = {str(x[1]): x for x in children(parse(raw.decode()), "symbol")}
        records.append({"library": library, "sha256": hashlib.sha256(raw).hexdigest(),
                        "source": "Official KiCad 9.0.9 Docker library; image digest in HW_SCHEMATIC_CORE.md"})
    index = libraries[library]
    sym = copy.deepcopy(index[original])
    extends = child(sym, "extends")
    if extends:
        base = copy.deepcopy(index[str(extends[1])])
        overrides = {str(x[1]): x for x in children(sym, "property")}
        base = [x for x in base if not (isinstance(x, list) and x[0] == "property" and str(x[1]) in overrides)]
        base.extend(overrides.values())
        sym = base
    oldname = str(sym[1])
    sym[1] = Quoted("Power8GDI_Core:" + name)
    for unit in children(sym, "symbol"):
        unit[1] = Quoted(str(unit[1]).replace(oldname + "_", name + "_"))
        for pin in children(unit, "pin"):
            if name == "STM32F767IIT6" and str(child(pin, "name")[1]).startswith("VCAP"):
                # ST DS11532 Fig25: these are internal regulator outputs.
                pin[1] = "power_out"
    for prop in children(sym, "property"):
        if prop[1] == "Value":
            prop[2] = Quoted(name)
    output.append(dump(sym))
(HERE / "core_sources").mkdir(exist_ok=True)
(HERE / "core_sources/core_selected.kicad_sym").write_text(
    '(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n' + "\n".join(output) + ')\n', encoding="utf-8")
(HERE / "core_sources/kicad_provenance.json").write_text(json.dumps(records, indent=2)+"\n", encoding="utf-8")
print("Extracted", [x[2] for x in selected])
