"""Explicit provenance refresh; never invoked by the offline verification runner."""
from pathlib import Path
import hashlib,json,subprocess,urllib.request
from source_provenance import text_fingerprints
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
DOCS=[
 ('tpic8101','https://www.ti.com/lit/ds/symlink/tpic8101.pdf','TI SLIS110C, March2015','pinout; input network; SPI digital output; clock and supply requirements'),
 ('cj125','https://www.bosch-semiconductors.com/media/automotive_systems_ics/pdf_1/ic_engine_management/cj125_product_info_2019-02.pdf','Bosch product information, February2019','32-pin drawing and proposed analogue application; incomplete device specification'),
 ('sn74ahct244-q1','https://www.ti.com/lit/ds/symlink/sn74ahct244-q1.pdf','TI SCLS529E, August2024','5V TTL-compatible input buffers and output-enable truth table'),
 ('sn74lvc1g125-q1','https://www.ti.com/lit/ds/symlink/sn74lvc1g125-q1.pdf','TI SGES002F, August2026','5.5V-tolerant input, CS-controlled return buffer and current orderable code'),
 ('mcp3204','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/21298e.pdf','Microchip DS21298E,2008','14-pin MCP3204, four ADC channels, clock/range/temperature limits'),
 ('tlv9004-q1','https://www.ti.com/lit/gpn/TLV9004-Q1','TI SBOS980G, April2026','quad unity buffer,14-pin PW package, high-impedance CJ output load'),
 ('asem','https://abracon.com/Oscillators/ASEM.pdf','Abracon ASEM RevP, January8,2025','own8MHz oscillator,15pF load ceiling and temperature grade'),
]
FILES=['lambda-x2/readme.md','wideband-F103/readme.md','classic-designs/rusefi_hardware_history/CJ125_board_rev00.20/known_issues.txt','classic-designs/knock_VR_Art_ELectro/cps_vrs_io_1.sch']
def main():
    work=HERE/'work';work.mkdir(exist_ok=True);docs=[]
    for key,url,revision,use in DOCS:
        path=work/(key+'.pdf')
        if not path.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            path.write_bytes(urllib.request.urlopen(req,timeout=60).read())
        raw=path.read_bytes()
        if not raw.startswith(b'%PDF'):raise RuntimeError('Not a PDF: '+key)
        docs.append({'id':key,'url':url,'revision_reviewed':revision,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'use':use,'license':'Manufacturer copyrighted technical reference; PDF not redistributed in this commit'})
    files=[]
    for name in FILES:
        raw=(ROOT/name).read_bytes()
        blob=subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=ROOT,text=True).strip()
        sha,actual_blob=text_fingerprints(raw)
        if actual_blob!=blob:raise RuntimeError('Source differs from pinned Git blob: '+name)
        files.append({'path':name,'git_blob':blob,'lf_sha256':sha,'disposition':'Read-only comparison; no original board file modified or copied into aux'})
    result={'schema_version':1,'review_date':'2026-10-21','review_base':'daf7c81','documents':docs,'source_files':files,'sensor_connector':{'url':'https://www.bosch-motorsport.com/content/downloads/Raceparts/en-GB/51865867208058251.html','publisher':'Bosch Motorsport','device':'LSU4.9','pins':{'1':'IP','2':'VM','3':'H-','4':'H+','5':'IA trim','6':'UN'}},'attribution':'Application networks derived from TI and Bosch primary documentation; independent project implementation does not imply independently invented analogue topology. No NXP evaluation schematic is copied. Existing fork upstream licensing unresolved; no new license is asserted. KiCad standard library footprints are referenced under their own license and exception.'}
    result['schema_version']=2
    result['source_text_hash_policy']='CRLF_TO_LF_ONLY'
    (HERE/'sources.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f'Captured {len(docs)} primary document hashes and {len(files)} read-only upstream blobs')
if __name__=='__main__':main()
