"""Optional online evidence refresh; PDFs stay in ignored work/, hashes are reviewable."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import urllib.request

HERE=Path(__file__).resolve().parent
SOURCES=[
 ('TPS3431-Q1','https://www.ti.com/lit/ds/symlink/tps3431-q1.pdf','SNVSB67A, October 2021','pin functions p3; timing pp6,14; ENOUT wiring p1; DRB package land pattern'),
 ('TPS3808-Q1','https://www.ti.com/lit/ds/symlink/tps3808-q1.pdf','SBVS085J, June 2017','pin functions p3; 3.07 V G33 threshold; CT open 20 ms; open-drain reset, MR'),
 ('SN74LVC1G17-Q1','https://www.ti.com/lit/ds/symlink/sn74lvc1g17-q1.pdf','SCES663E, October 2025','DBV pin map p3; Schmitt and Ioff; orderable DBV and package outline'),
 ('SN74LVC2G74-Q1','https://www.ti.com/lit/ds/symlink/sn74lvc2g74-q1.pdf','SCES563C, April 2008','pins p1; Qbar=3, Q=5; function table p2; input transition limits p4; DCU package'),
 ('SN74LVC244A-Q1','https://www.ti.com/lit/ds/symlink/sn74lvc244a-q1.pdf?ts=1776262857322','SCAS790D, February 2026','pin table pp3-4; Ioff and IOZ p7; OE pullup p11; truth table p12; PW0020A package'),
]

def get(source):
    name,url,revision,evidence=source
    req=urllib.request.Request(url,headers={'User-Agent':'Power8GDI evidence audit'})
    data=urllib.request.urlopen(req,timeout=60).read()
    if not data.startswith(b'%PDF'):raise ValueError('Expected manufacturer PDF: '+name)
    (HERE/'work'/(name+'.pdf')).write_bytes(data)
    return {'id':name,'url':url,'reviewed_revision':revision,'retrieved_utc_date':'2026-10-21','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'evidence':evidence,'license_note':'Manufacturer copyrighted datasheet; PDF not committed; factual pin/parameter transcription only.'}

def main():
    (HERE/'work').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool: docs=list(pool.map(get,SOURCES))
    result={'schema_version':1,'design_origin':'Project-authored safety interconnect and symbols; schlib.py adapted from project core_schlib.py, not GDI4 source','manufacturer_sources':docs,'footprints':{'source':'Official KiCad 9.0.9 Docker library; installed files hashed in footprint_manifest.json','license':'CC-BY-SA-4.0 with KiCad Libraries Exception','license_url':'https://www.kicad.org/libraries/license/','redistribution':'Only footprint IDs/hashes/pad identifiers committed in this increment; no footprint files copied'},'container':{'image':'kicad/kicad:9.0','verified_version':'9.0.9','digest':'sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729'},'release_status':'BLOCKED','no_hardware_action':True}
    (HERE/'provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Recorded manufacturer sources and hashes:',len(docs))

if __name__=='__main__':main()
