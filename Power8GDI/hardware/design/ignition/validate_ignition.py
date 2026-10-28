"""Create an explicit external-interface fixture and audit real KiCad XML nets.

Fixture powers and commands represent off-sheet parent supplies/MCU only.
They are not production components and are never returned by make_ignition().
Run `prepare`, kicad-cli exports, then `audit --footprints /usr/share/kicad/footprints`.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from core_schlib import Sheet, box_symbol, parse, children, child, uid
from build_core_schematic import load_symbols
from build_ignition import make_ignition, generate, calculations


def prepare():
    generate()
    syms=load_symbols()
    root=Sheet("ignition_validation", "EXTERNAL INTERFACE FIXTURE - NOT PRODUCTION BOM",paper="A2")
    root.uuid=uid("Power8GDI_Core")
    leaves=make_ignition(syms,root.uuid)
    for i,s in enumerate(leaves):
        root.add_child(s,25+(i%3)*180,40+(i//3)*65,width=145,height=40)
    # Fixture lives next to leaves; production root lives one directory above.
    root.items=[item.replace('"ignition/','"') for item in root.items]
    names=[("+3V3","power_out"),("+5V_CORE","power_out"),("GND","power_out")]
    names += [(f"IGN{i}","output") for i in range(1,7)]
    names += [("HW_ACTUATOR_ENABLE","output"),("IGN_OC_OK","input")]
    names += [(f"HARNESS_IGN{i}","passive") for i in range(1,7)]
    pins=[(str(i+1),name,kind,-20.32,48.26-i*5.08,0) for i,(name,kind) in enumerate(names)]
    fixture=box_symbol("IGN_External_Test_Fixture",pins,width=35.56,height=110,prefix="X")
    root.component(fixture,"X5599","EXTERNAL_TEST_FIXTURE_ONLY",100,310,
        {str(i+1):name for i,(name,kind) in enumerate(names)})
    root.text("Abstract off-sheet supplies, MCU commands and harness terminals.\nNOT part of production BOM. No ERC exclusions or PWR_FLAGs.\nThis isolated ERC cannot validate parent power sequencing, return layout,\ncoil selection, thermal behavior or the global safety latch.",180,280)
    root.write(HERE)
    all_symbols={symbol.name:symbol for s in [root]+leaves for symbol in s.symbols.values()}
    library='(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'
    library+='\n'.join(symbol.body.replace('"Power8GDI_Core:'+name+'"','"'+name+'"',1) for name,symbol in all_symbols.items())+'\n)\n'
    (HERE/"ignition_symbols.kicad_sym").write_text(library,encoding="utf-8")
    (HERE/"sym-lib-table").write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/ignition_symbols.kicad_sym")(options "")(descr "Ignition validation symbols")))\n',encoding="utf-8")
    (HERE/"ignition_validation.kicad_pro").write_text('{"meta":{"filename":"ignition_validation.kicad_pro","version":1}}\n',encoding="utf-8")
    (HERE/"reports").mkdir(exist_ok=True)


def audit(footprints):
    data=json.loads((HERE/"ignition_manifest.json").read_text())
    manifest={p["ref"]:p for p in data["parts"]}
    xml=ET.parse(HERE/"reports/ignition.net.xml").getroot()
    actual={}
    components={c.attrib["ref"]:c for c in xml.findall("components/comp")}
    for net in xml.findall("nets/net"):
        for node in net.findall("node"):
            actual[(node.attrib["ref"],node.attrib["pin"])]=net.attrib["name"].lstrip("/")
    assert set(components)==set(manifest)|{"X5599"},"Export component mismatch"
    for ref,p in manifest.items():
        assert components[ref].findtext("value")==p["value"],ref
        for pin,net in p["pins"].items():
            assert actual.get((ref,pin))==net,(ref,pin,net,actual.get((ref,pin)))
    # Independent datasheet-sensitive net expectations; no manifest-only assertions.
    for ch in range(1,7):
        n=5420+(ch-1)*20
        p=f"IGN{ch}"
        expected={f"Q{n}":{"1":p+"_GATE","2":f"HARNESS_IGN{ch}","3":p+"_SHUNT_HI"},
            f"U{n}":{"1":p,"2":"GND","3":p+"_SET","4":p+"_DIV","5":"+3V3","6":p+"_WINDOW"},
            f"U{n+1}":{"1":p,"2":"GND","3":p+"_WINDOW","4":p+"_GUARDED","5":"+3V3","6":"IGN_SAFE_EN"},
            f"U{n+2}":{"1":p+"_SHUNT_HI","2":"GND","3":p+"_ILIMIT","4":"+3V3","5":"IGN_OC_OK","6":"+3V3","8":"GND","9":"+3V3"}}
        for ref,pins in expected.items():
            for pin,net in pins.items(): assert actual[(ref,pin)]==net,(ref,pin)
        collector_nodes={key for key,net in actual.items() if net==f"HARNESS_IGN{ch}"}
        assert collector_nodes=={(f"Q{n}","2"),("X5599",str(13+ch))},collector_nodes
        pair=(ch-1)//2
        assert actual[(f"U{5402+pair}","2" if ch%2 else "4")]==p+"_GUARDED"
        assert actual[(f"U{5402+pair}","7" if ch%2 else "5")]==p+"_DRIVE"
        assert actual[(f"U{5402+pair}","1" if ch%2 else "8")]=="IGN_SAFE_EN"
        # Floating timing-selection pins must remain intentionally unconnected.
        for pin in ("7","10"):
            assert "unconnected" in actual.get((f"U{n+2}",pin),"unconnected")
    oc_members={ref for (ref,pin),net in actual.items() if net=="IGN_OC_OK" and ref.startswith("U")}
    assert oc_members=={"U5400"}|{f"U{5422+i*20}" for i in range(8)}
    assert actual[("U5401","1")]=="HW_ACTUATOR_ENABLE"
    assert actual[("U5401","3")]=="IGN_OC_OK_CLEAN"
    assert actual[("U5401","4")]=="IGN_SAFE_EN"
    # Footprint pad inventory + source hashes; standards are installed KiCad 9.
    footprint_report={}
    for fp in sorted({p["footprint"] for p in manifest.values()}):
        lib,name=fp.split(":")
        path=Path(footprints)/(lib+".pretty")/(name+".kicad_mod")
        raw=path.read_bytes()
        expr=parse(raw.decode())
        pads={str(p[1]):{"at":child(p,"at")[1:3],"size":child(p,"size")[1:3]} for p in children(expr,"pad") if str(p[1])}
        for ref,p in manifest.items():
            if p["footprint"]==fp:
                assert set(p["pins"])<=set(pads),(ref,fp,set(p["pins"])-set(pads))
        footprint_report[fp]={"sha256":hashlib.sha256(raw).hexdigest(),"pads":pads}
    # D2PAK pad2 must be the broad tab, with gate/emitter smaller and separated.
    to263=footprint_report["Package_TO_SOT_SMD:TO-263-2"]["pads"]
    assert float(to263["2"]["size"][0])>float(to263["1"]["size"][0])
    assert abs(abs(float(to263["1"]["at"][1])-float(to263["3"]["at"][1]))-5.08)<.01
    report={"status":"PASS","components_excluding_fixture":len(manifest),"mapped_pins":sum(len(p["pins"]) for p in manifest.values()),"net_count":len(xml.findall("nets/net")),"footprints":footprint_report,"calculations":calculations()}
    (HERE/"reports/net_and_footprint_audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("footprints","calculations")},indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","audit"])
    parser.add_argument("--footprints",default="/usr/share/kicad/footprints")
    args=parser.parse_args()
    prepare() if args.action=="prepare" else audit(args.footprints)
