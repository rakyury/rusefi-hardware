"""Small deterministic KiCad schematic writer; electrical pins remain explicit.

No ERC exclusions or synthetic power flags are emitted. Not an electrical solver.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import uuid

NS = uuid.UUID("d612b05b-5ba1-58a0-a258-c67f211e59ab")


def uid(key):
    return str(uuid.uuid5(NS, str(key)))


def q(value):
    return json.dumps(str(value), ensure_ascii=False)


def num(value):
    return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"


def snap(value):
    return round(round(value / 1.27) * 1.27, 4)


class Quoted(str):
    pass


def parse(text):
    tokens = iter(re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', text))
    def read(token):
        if token == "(":
            result = []
            for item in tokens:
                if item == ")":
                    return result
                result.append(read(item))
            raise ValueError("Unclosed expression")
        return Quoted(json.loads(token)) if token.startswith('"') else token
    result = read(next(tokens))
    if next(tokens, None) is not None:
        raise ValueError("Trailing expression")
    return result


def dump(item):
    if isinstance(item, list):
        return "(" + " ".join(dump(x) for x in item) + ")"
    return q(item) if isinstance(item, Quoted) else str(item)


def children(expr, kind):
    return [x for x in expr if isinstance(x, list) and x[0] == kind]


def child(expr, kind):
    return next((x for x in expr if isinstance(x, list) and x[0] == kind), None)


def effect(size=1.27, justify="", hidden=False):
    return (f"(effects (font (size {num(size)} {num(size)}))"
            + (f" (justify {justify})" if justify else "")
            + (" (hide yes)" if hidden else "") + ")")


class Symbol:
    def __init__(self, name, body, footprint="", description=""):
        self.name, self.body = name, body
        self.footprint, self.description = footprint, description
        expr = parse(body)
        self.pins = {}
        for unit in children(expr, "symbol"):
            for pin in children(unit, "pin"):
                at = child(pin, "at")
                number = str(child(pin, "number")[1])
                self.pins[number] = {
                    "name": str(child(pin, "name")[1]), "type": pin[1],
                    "x": float(at[1]), "y": float(at[2]), "angle": int(at[3]),
                }


def box_symbol(name, pins, footprint="", width=15.24, height=15.24, prefix="U"):
    """pins: (number, name, electrical_type, x, y, inward_angle)."""
    name = name.split(":")[-1]
    body = [f'(symbol {q("Power8GDI_Aux:" + name)} (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
            f'(property "Reference" {q(prefix)} (at 0 {num(height/2+2.54)} 0) {effect()})',
            f'(property "Value" {q(name)} (at 0 {num(-height/2-2.54)} 0) {effect()})',
            f'(property "Footprint" {q(footprint)} (at 0 0 0) {effect(hidden=True)})',
            f'(symbol {q(name+"_0_1")} (rectangle (start {num(-width/2)} {num(height/2)}) (end {num(width/2)} {num(-height/2)}) (stroke (width 0.254) (type default)) (fill (type background))))',
            f'(symbol {q(name+"_1_1")}']
    for number, pinname, kind, x, y, angle in pins:
        body.append(f'(pin {kind} line (at {num(x)} {num(y)} {angle}) (length 2.54) (name {q(pinname)} {effect(1.016)}) (number {q(number)} {effect(1.016)}))')
    body.append("))")
    return Symbol(name, "\n".join(body), footprint)


class Sheet:
    def __init__(self, name, title, root=None, paper="A3"):
        self.name, self.title, self.paper = name, title, paper
        self.uuid = uid(name)
        self.root = root or self.uuid
        self.project = "Power8GDI_Core"
        self.sheet_id = uid("sheet:" + name)
        self.symbols, self.items, self.parts = {}, [], []

    def _id(self, key):
        return uid(self.name + ":" + str(key))

    def wire(self, x1, y1, x2, y2):
        self.items.append(f'(wire (pts (xy {num(x1)} {num(y1)}) (xy {num(x2)} {num(y2)})) (stroke (width 0) (type default)) (uuid {q(self._id(("wire",x1,y1,x2,y2)))}))')

    def label(self, name, x, y, angle=0, global_=False, shape="bidirectional"):
        kind = "global_label" if global_ else "label"
        extra = f" (shape {shape})" if global_ else ""
        justify = "right bottom" if global_ and angle in (0,90) else "left bottom"
        self.items.append(f'({kind} {q(name)}{extra} (at {num(x)} {num(y)} {angle}) {effect(1.016, justify)} (uuid {q(self._id((kind,name,x,y)))}))')

    def text(self, text, x, y, size=1.27):
        self.items.append(f'(text {q(text)} (at {num(x)} {num(y)} 0) {effect(size, "left top")} (uuid {q(self._id(("text",text,x,y)))}))')

    def hport(self, name, x, y, shape="input"):
        x,y=snap(x),snap(y)
        self.items.append(f'(hierarchical_label {q(name)} (shape {shape}) (at {num(x)} {num(y)} 0) {effect(1.27, "left")} (uuid {q(self._id(("hport",name)))}))')
        self.wire(x, y, x+10.16, y)
        self.label(name, x+10.16, y, global_=True, shape=shape)

    def component(self, symbol, ref, value, x, y, nets, *, footprint=None, note="", dnp=False, global_nets=True):
        x,y=snap(x),snap(y)
        self.symbols[symbol.name] = symbol
        fp = symbol.footprint if footprint is None else footprint
        iid = self._id(ref)
        path = "/" + self.root + ("/" + self.sheet_id if self.root != self.uuid else "")
        extent = max(abs(p["y"]) for p in symbol.pins.values())
        if ref.startswith('U'):
            extent = max(5.08, extent + 2.54)
        props = [f'(property "Reference" {q(ref)} (at {num(x+4 if extent<5 else x)} {num(y-1.27 if extent<5 else y-extent-2.54)} 0) {effect(justify="left" if extent<5 else "")})',
                 f'(property "Value" {q(value)} (at {num(x+4 if extent<5 else x)} {num(y+1.27 if extent<5 else y+extent+2.54)} 0) {effect(justify="left" if extent<5 else "")})',
                 f'(property "Footprint" {q(fp)} (at {num(x)} {num(y)} 0) {effect(hidden=True)})',
                 f'(property "Design note" {q(note)} (at {num(x)} {num(y)} 0) {effect(hidden=True)})']
        pins = " ".join(f'(pin {q(p)} (uuid {q(self._id(ref+":"+p))}))' for p in symbol.pins)
        self.items.append(f'(symbol (lib_id {q("Power8GDI_Aux:"+symbol.name)}) (at {num(x)} {num(y)} 0) (unit 1) (in_bom yes) (on_board yes) (dnp {"yes" if dnp else "no"}) (uuid {q(iid)}) {" ".join(props)} {pins} (instances (project {q(self.project)} (path {q(path)} (reference {q(ref)}) (unit 1)))))')
        for number, pin in symbol.pins.items():
            px, py = x + pin["x"], y - pin["y"]
            net = nets.get(number)
            if net is None:
                self.items.append(f'(no_connect (at {num(px)} {num(py)}) (uuid {q(self._id(ref+":"+number+":nc"))}))')
                continue
            rad = math.radians(pin["angle"])
            ex = round(px - 7.62 * math.cos(rad), 4)
            ey = round(py + 7.62 * math.sin(rad), 4)
            self.wire(px, py, ex, ey)
            self.label(net, ex, ey, angle=pin["angle"], global_=global_nets)
        self.parts.append({"ref":ref,"value":value,"footprint":fp,"pins":nets,"dnp":dnp,"note":note,"sheet":self.name})

    def add_child(self, sheet, x, y, width=65, height=40, ports=()):
        x,y,width,height=map(snap,(x,y,width,height))
        fields = [f'(property "Sheetname" {q(sheet.title)} (at {num(x)} {num(y-1.27)} 0) {effect(1.27, "left")})',
                  f'(property "Sheetfile" {q(sheet.name+".kicad_sch")} (at {num(x)} {num(y+height+1.27)} 0) {effect(1.27, "left")})']
        for i,(name,direction) in enumerate(ports):
            py=y+7.62+i*7.62
            fields.append(f'(pin {q(name)} {direction} (at {num(x)} {num(py)} 180) {effect(1.27, "left")} (uuid {q(uid(sheet.name+":"+name))}))')
            self.wire(x,py,x-10.16,py)
            self.label(name,x-10.16,py,global_=True,shape=direction)
        self.items.append(f'(sheet (at {num(x)} {num(y)}) (size {num(width)} {num(height)}) (stroke (width 0.254) (type default)) (fill (color 0 0 0 0)) (uuid {q(sheet.sheet_id)}) {" ".join(fields)} (instances (project {q(self.project)} (path {q("/"+self.uuid)} (page {q(str(len(self.items)))})))))')

    def write(self, directory):
        lib="\n".join(s.body for s in self.symbols.values())
        text=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(self.uuid)}) (paper {q(self.paper)}) (title_block (title {q(self.title)}) (rev "Engineering draft 0.1") (comment 1 "UNQUALIFIED: no manufacturing or engine approval"))\n(lib_symbols\n{lib}\n)\n'+"\n".join(self.items)+f'\n(sheet_instances (path "/" (page "1"))))\n'
        path=Path(directory)/(self.name+".kicad_sch")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding="utf-8",newline="\n")
