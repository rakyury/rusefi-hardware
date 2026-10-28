"""Render views from CAD STL solids with VTK. These are CAD-derived mockup views.
Run using: python mechanical/render_views.py --input-dir mechanical/build/assembly
"""
from pathlib import Path
import argparse
from functools import partial
import json

HERE=Path(__file__).resolve().parent
colors={
 'Base':(0.22,0.27,0.33),'Lid':(0.29,0.34,0.4),'PCB':(0.05,0.32,0.27),
 'MCU_F7':(0.07,0.09,0.12),'PT2001_A':(0.07,0.09,0.12),'PT2001_B':(0.07,0.09,0.12),
 'GDI_BOOST_A':(0.57,0.58,0.61),'GDI_BOOST_B':(0.57,0.58,0.61),
 'LOW_SIDE_24':(0.1,0.12,0.16),'H_BRIDGE_A':(0.08,0.09,0.11),
 'H_BRIDGE_B':(0.08,0.09,0.11),'KNOCK_ANALOG':(0.17,0.19,0.24),
 'POWER_IN':(0.45,0.47,0.49),'LIN_CAN':(0.12,0.14,0.18),
}
def render(name,title,subtitle,cam,focus=(0,0,13),explode=False,show_lid=True,pcb_only=False,*,source_dir,output_dir,parts):
 import vtk
 from PIL import Image,ImageDraw,ImageFont
 OUT=output_dir
 rend=vtk.vtkRenderer();rend.SetBackground(0.045,0.075,0.12)
 rend.GradientBackgroundOn();rend.SetBackground2(0.10,0.15,0.22)
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(1500,1050);win.SetMultiSamples(8)
 win.AddRenderer(rend)
 for n in parts:
  if pcb_only and n in {'Base','Lid'}:continue
  if n=='Lid' and not show_lid:continue
  reader=vtk.vtkSTLReader(); reader.SetFileName(str(source_dir/'stl'/f'{n}.stl'));reader.Update()
  normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(reader.GetOutputPort());normals.SetFeatureAngle(45)
  normals.SplittingOn();normals.ConsistencyOn();normals.Update()
  mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
  actor=vtk.vtkActor();actor.SetMapper(mapper)
  actor.GetProperty().SetColor(*colors.get(n,(0.09,0.12,0.16)));actor.GetProperty().SetAmbient(0.23)
  actor.GetProperty().SetDiffuse(0.66);actor.GetProperty().SetSpecular(0.38)
  actor.GetProperty().SetSpecularPower(45)
  if n=='PCB': actor.GetProperty().SetSpecular(0.15)
  if explode:
   if n=='Lid':actor.SetPosition(0,0,37)
   if n!='Lid' and n!='Base':actor.AddPosition(0,0,10)
  rend.AddActor(actor)
 light=vtk.vtkLight();light.SetLightTypeToSceneLight();light.SetPosition(250,-160,360);light.SetFocalPoint(0,0,0);light.SetIntensity(1.25)
 rend.AddLight(light)
 light2=vtk.vtkLight();light2.SetLightTypeToSceneLight();light2.SetPosition(-220,210,300);light2.SetFocalPoint(0,0,0);light2.SetIntensity(.65);rend.AddLight(light2)
 camera=rend.GetActiveCamera();camera.SetFocalPoint(*focus)
 camera.SetPosition(*cam);camera.SetViewUp(0,0,1);camera.ParallelProjectionOn()
 camera.SetParallelScale(164 if not pcb_only else 151)
 rend.SetActiveCamera(camera)
 rend.ResetCameraClippingRange();win.Render()
 frame=vtk.vtkWindowToImageFilter();frame.SetInput(win);frame.SetInputBufferTypeToRGB();frame.ReadFrontBufferOff();frame.Update()
 w=vtk.vtkPNGWriter();w.SetInputConnection(frame.GetOutputPort());w.SetFileName(str(OUT/f'{name}_raw.png'));w.Write()
 img=Image.open(OUT/f'{name}_raw.png').convert('RGB')
 (OUT/f'{name}_raw.png').unlink()
 dr=ImageDraw.Draw(img)
 def font(size,bold=False):
  candidates=[Path('C:/Windows/Fonts')/('segoeuib.ttf' if bold else 'segoeui.ttf'),
              Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
  for candidate in candidates:
   if candidate.is_file():return ImageFont.truetype(str(candidate),size)
  return ImageFont.load_default(size=size)
 f1=font(36,True);f2=font(20)
 dr.rounded_rectangle((28,30,950,139),radius=14,fill=(9,21,34))
 dr.text((50,47),title,font=f1,fill=(240,246,253))
 dr.text((52,103),subtitle,font=f2,fill=(152,189,204))
 dr.rounded_rectangle((28,976,1470,1035),radius=11,fill=(9,21,34))
 dr.text((50,993),'POWER8GDI  /  PRELIMINARY CAD ENVELOPE — NOT PRODUCTION HARDWARE',font=f2,fill=(255,202,139))
 img.save(OUT/f'{name}.png',quality=96)
 win.Finalize()
 print(name, (OUT/f'{name}.png').stat().st_size)

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--input-dir',type=Path,default=HERE/'build'/'assembly')
 parser.add_argument('--output-dir',type=Path,default=HERE/'build'/'renders')
 args=parser.parse_args(argv)
 manifest=json.loads((args.input_dir/'assembly_manifest.json').read_text(encoding='utf-8'))
 parts=manifest['solids']
 for part in parts:
  if not (args.input_dir/'stl'/f'{part}.stl').is_file():raise FileNotFoundError(f'Missing STL: {part}')
 args.output_dir.mkdir(parents=True,exist_ok=True)
 draw=partial(render,source_dir=args.input_dir,output_dir=args.output_dir,parts=parts)
 draw('01_assembly_isometric','Power8GDI Rev A / Assembly','Base + lid + 4 x 34-pin connector envelope',(370,-400,285))
 draw('02_assembly_rear','Enclosure / Rear view','Solid enclosure envelope / lid fasteners conceptual',(-330,330,210))
 draw('03_connectors_front','Connector face / Concept','Four 34-pin connector body envelopes; TE geometry pending',(65,-450,124),focus=(0,-38,24))
 draw('04_exploded','Power8GDI / Exploded assembly','Board and component spatial mockup; lid lifted',(360,-360,310),focus=(0,0,45),explode=True)
 draw('05_pcb_top','PCB envelope / Top side','Component placement concept only; NO pads or routed copper',(230,-230,360),focus=(0,0,12),show_lid=False,pcb_only=True)
 draw('06_pcb_back','PCB envelope / Underside','Board envelope and connector bodies; no electrical layout',(285,200,-290),focus=(0,0,11),show_lid=False,pcb_only=True)
 return 0

if __name__=='__main__':raise SystemExit(main())
