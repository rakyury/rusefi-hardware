"""Container-side pin/pad and footprint provenance extraction; no PCB mutation."""
from pathlib import Path
import hashlib
import json
from schlib import parse,children

HERE=Path(__file__).resolve().parent

def main():
    parts=json.loads((HERE/'parts.json').read_text());manifest={}
    for p in parts:
        fp=p['footprint']
        if fp in manifest:continue
        lib,name=fp.split(':')
        path=Path('/usr/share/kicad/footprints')/(lib+'.pretty')/(name+'.kicad_mod')
        raw=path.read_bytes();expr=parse(raw.decode())
        pads=children(expr,'pad')
        manifest[fp]={'library_path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'pads':sorted(set(str(x[1]) for x in pads)),'source':'KiCad 9.0.9 official container footprint library; CC-BY-SA-4.0 with KiCad Libraries Exception','parts':[p['ref'] for p in parts if p['footprint']==fp]}
    (HERE/'footprint_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Footprint evidence: {len(manifest)} unique installed library files')

if __name__=='__main__':main()
