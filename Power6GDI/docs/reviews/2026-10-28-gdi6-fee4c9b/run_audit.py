import json,subprocess,sys,hashlib
from pathlib import Path
root=Path('/src/Power8GDI/hardware/design'); out=Path('/audit')
board=root/'board/gdi6_candidate/Power8GDI_Review.kicad_pcb'
commands=[('pad_validation.json',[sys.executable,str(root/'board/verify_board.py'),str(board),str(root/'core.net')],{0}),
 ('drc_run.log',[sys.executable,str(root/'board/run_drc.py'),str(board),'--output',str(out/'native_drc.json')],{5}),
 ('coverage_run.log',[sys.executable,str(root/'board/summarize_drc.py'),str(board),str(out/'native_drc.json'),str(out/'net_coverage.json')],{0})]
records=[]
for name,command,expected in commands:
 result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (out/name).write_text(result.stdout)
 records.append({'command':command,'returncode':result.returncode,'expected':sorted(expected)})
 print(name,result.returncode,result.stdout[:1200],flush=True)
 if result.returncode not in expected:raise RuntimeError(name+' unexpected result')
(out/'commands.json').write_text(json.dumps(records,indent=2))
manifest=json.loads((board.parent/'artifact_manifest.json').read_text());checks=[]
for rel,item in manifest['files'].items():
 path=root/Path(rel.replace('\\','/'));data=path.read_bytes()
 if path.suffix.lower() not in ('.png','.pdf'):data=data.replace(b'\r\n',b'\n')
 checks.append({'file':rel,'matches':hashlib.sha256(data).hexdigest()==item['sha256']})
(out/'manifest_checks.json').write_text(json.dumps(checks,indent=2))
assert all(x['matches'] for x in checks)
print('manifest checks PASS',len(checks),flush=True)
