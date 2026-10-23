"""Author the four real harness connectors using the shared schematic writer."""
import argparse
import csv
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def build(helper_dir, pinout):
    sys.path.insert(0,str(helper_dir))
    from core_schlib import Sheet, box_symbol, q
    aliases={r['pinout_net']:r['board_net'] for r in csv.DictReader((HERE/'connector_aliases.csv').open())}
    rows=list(csv.DictReader(Path(pinout).open()))
    rootid=json.loads((helper_dir/'core_manifest.json').read_text())['root_uuid']
    sheet=Sheet('board/connectors','Power8GDI TE34 harness boundary / UNQUALIFIED',root=rootid,paper='A2')
    pins=[]
    for n in range(1,35):
        side=0 if n<=17 else 1
        pins.append((str(n),str(n),'passive',-12.7 if not side else 12.7,20.32-((n-1)%17)*2.54,0 if not side else 180))
    symbol=box_symbol('TE_6437288_1_34',pins,'Power8GDI_Board:TE_6437288-1_34way',width=20.32,height=45.72,prefix='J')
    for index,connector in enumerate('ABCD'):
        nets={r['position']:aliases.get(r['net'],'HARNESS_'+r['net']) for r in rows if r['connector']==connector}
        sheet.component(symbol,f'J60{index+1}','6437288-1 / KEY1 CANDIDATE',140+(index%2)*280,100+(index//2)*160,nets,
                        note='TE header C-9-1437287-8 A1 sheet2; numbering from mating housing RevP sheet3. Mechanical/continuity/keying review pending. Unimplemented circuits remain isolated HARNESS nets.')
    sheet.text('Four34-way SUPERSEAL1.0 headers. 4xKEY1 is provisional and NOT protected against cross-mating.\nHARNESS_ prefix separates vehicle-side pins from MCU-side logic. Only connector_aliases.csv joins reviewed circuits.\nNo pin current/thermal qualification, high-side bank allocation, loom approval, EMC or engine approval.',25.4,20)
    sheet.write(HERE.parent)
    path=HERE/'connectors.kicad_sch'
    path.write_text(path.read_text().replace('Power8GDI_Core:TE_6437288_1_34','Power8GDI_Board:TE_6437288_1_34'))
    body=symbol.body.replace(q('Power8GDI_Core:TE_6437288_1_34'),q('TE_6437288_1_34'),1)
    (HERE/'Power8GDI_Board.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+body+')\n')
    (HERE/'sym-lib-table').write_text('(sym_lib_table (version 7)(lib(name "Power8GDI_Board")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Board.kicad_sym")(options "")(descr "TE drawing derived connector symbol")))\n')
    (HERE/'fp-lib-table').write_text('(fp_lib_table (version 7)(lib(name "Power8GDI_Board")(type "KiCad")(uri "${KIPRJMOD}/Power8GDI_Board.pretty")(options "")(descr "TE drawing derived connector land pattern")))\n')
    (HERE/'connector_manifest.json').write_text(json.dumps({'parts':sheet.parts,'aliases':aliases,'root_uuid':rootid},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper-dir',type=Path,default=HERE.parent)
    parser.add_argument('--pinout',type=Path,default=HERE.parents[2]/'pinout/power8gdi_revA_pinout.csv')
    args=parser.parse_args();build(args.helper_dir,args.pinout)
