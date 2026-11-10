"""Check exported KiCad connectivity, without treating an ERC export as release approval."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from logic_power.check_logic_power import validate as validate_logic_power


def verify(xml_path, manifest_path=HERE/"core_manifest.json", erc_path=None):
    doc=ET.parse(xml_path).getroot()
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    components={}
    errors=[]
    for item in doc.findall("components/comp"):
        ref=item.get("ref")
        if ref in components: errors.append("Duplicate component "+ref)
        components[ref]=item
    endpoints={}
    net_nodes={}
    for net in doc.findall("nets/net"):
        name=net.get("name")
        net_nodes[name]=set()
        for node in net.findall("node"):
            endpoint=(node.get("ref"),node.get("pin"))
            if endpoint in endpoints: errors.append("Pad in two nets: "+str(endpoint))
            endpoints[endpoint]=name
            net_nodes[name].add(endpoint)
    for part in manifest["parts"]:
        ref=part["ref"]
        comp=components.get(ref)
        if comp is None:
            errors.append("Missing component "+ref)
            continue
        for field in ("value","footprint"):
            if comp.findtext(field)!=part[field]: errors.append(ref+" "+field+" differs from manifest")
        for pin,net in part["pins"].items():
            if endpoints.get((ref,pin))!=net:
                errors.append(f"{ref}.{pin}: expected {net}, got {endpoints.get((ref,pin))}")
        dnp=any(p.get("name")=="dnp" for p in comp.findall("property"))
        if dnp!=part["dnp"]: errors.append(ref+" DNP differs from manifest")
    # Manufacturer-derived invariants, independently written from the generator.
    for pad in (15,23,36,49,62,72,82,91,103,127,136,159,172,6,114,149,171):
        if endpoints.get(("U101",str(pad)))!="+3V3": errors.append("U101 supply pad "+str(pad))
    for pad in (14,22,37,48,61,71,90,102,113,126,135,148,158):
        if endpoints.get(("U101",str(pad)))!="GND": errors.append("U101 ground/BYPASS pad "+str(pad))
    for rail,expected in {"MCU_VCAP_1":{("U101","81"),("C115","1")},"MCU_VCAP_2":{("U101","125"),("C116","1")}}.items():
        if net_nodes.get(rail)!=expected: errors.append(rail+" may connect only its VCAP pad and capacitor")
    for pad,net in {"38":"+3V3_A","39":"+3V3_A","29":"MCU_HSE_IN","43":"CAN1_STB","44":"LIN1_EN","124":"SWDIO","137":"SWCLK","161":"SWO"}.items():
        if endpoints.get(("U101",pad))!=net: errors.append("U101 fixed pad "+pad+" expected "+net)
    for pad in (9,10,30):
        if not endpoints.get(("U101",str(pad)),"").startswith("unconnected-"):
            errors.append("Reserved oscillator pad unexpectedly connected: "+str(pad))
    if len({pin for ref,pin in endpoints if ref=="U101"})!=176: errors.append("Not all 176 MCU pads exported")
    for i in range(1,7):
        ref="Q"+str(5420+(i-1)*20)
        if endpoints.get((ref,"2"))!=f"HARNESS_IGN{i}": errors.append("Ignition collector boundary "+str(i))
        if endpoints.get((ref,"1"))!=f"IGN{i}_GATE": errors.append("Ignition gate bypass "+str(i))
        if any(r=="U101" for r,p in net_nodes.get(f"HARNESS_IGN{i}",set())): errors.append("MCU directly on ignition harness")
    # Fail if the integration silently restores the earlier incompatible 33 V TVS.
    if "D5201" not in components or "SMBJ24CA" not in components["D5201"].findtext("value",""):
        errors.append("LIN supply requires reviewed SMBJ24CA root protection candidate")
    try:
        validate_logic_power(endpoints,{r:c.findtext("value") for r,c in components.items()},
                             {r:c.findtext("footprint") for r,c in components.items()},integrated=True)
    except (AssertionError,KeyError) as error:
        errors.append("Logic power independent contract: "+str(error))
    counts=Counter()
    if erc_path:
        erc=json.loads(Path(erc_path).read_text(encoding="utf-8"))
        counts.update(v["type"] for sheet in erc["sheets"] for v in sheet["violations"])
        # Open supply semantics and unused boundaries remain visible release
        # gates. Library mismatches and electrical conflicts are regressions,
        # not something a successful XML export can excuse.
        unexpected=set(counts)-{'global_label_dangling'}
        if unexpected:errors.append('Unexpected integrated ERC findings: '+', '.join(sorted(unexpected)))
        allowed={f'PT{bank}_{name}' for bank in 'AB' for name in ['IRQ','OA_1','OA_2','FLAG_1','FLAG_2','DBG']}
        reviews=[]
        for sheet in erc['sheets']:
            for finding in sheet['violations']:
                names=[name for item in finding.get('items',[]) for name in re.findall(r"Global Label '([^']+)'",item.get('description',''))]
                if finding['type']=='global_label_dangling' and (len(names)!=1 or names[0] not in allowed):
                    errors.append('Unreviewed dangling global label: '+str(names))
                for name in names:
                    reviews.append({'net':name,'physical_endpoints':[f'{r}.{p}' for r,p in sorted(net_nodes.get(name,set()))],
                        'reason':'Retained source PT diagnostic/optional output has no consumer in six-cylinder target; not a supply or injector command',
                        'severity':finding['severity'],'excluded':False})
        (HERE/'erc_review.json').write_text(json.dumps({'errors':[e for e in errors if 'ERC' in e or 'dangling' in e],
            'warnings':reviews,'suppression_added':False},indent=2)+'\n')
    return {"schema_version":1,"structural_status":"FAIL" if errors else "PASS",
            "release_status":"BLOCKED","core_components":len(manifest["parts"]),
            "integrated_components":len(components),"checked_mcu_pads":176,
            "errors":errors,"erc_counts":dict(counts),
            "blockers":["Documented unused PT diagnostics remain as native warnings; no ERC exclusions",
                        "MCU GPIO AF/DMA/timing and added PH2/PH3 firmware are not qualified",
                        "3V3/5V allocated budgets pass; capacitor derating, hot regulator thermal and transient energy remain unqualified",
                        "Independent actuator inhibit and actual coil/injector/pump models unresolved",
                        "PCB routing, DRC, SI/EMC, environmental and fault tests not complete"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist",type=Path,default=HERE/"core.net")
    parser.add_argument("--erc",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--release",action="store_true",help="Fail closed while qualification is blocked")
    args=parser.parse_args()
    result=verify(args.netlist,erc_path=args.erc)
    body=json.dumps(result,indent=2)+"\n"
    if args.output: args.output.write_text(body,encoding="utf-8")
    print(body,end="")
    return 2 if args.release else int(result["structural_status"]!="PASS")


if __name__=="__main__": raise SystemExit(main())
