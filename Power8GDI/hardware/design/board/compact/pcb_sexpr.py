"""Minimal KiCad s-expression reader for footprint geometry without pcbnew.

Reads a .kicad_pcb and returns per-footprint reference, value, library id,
side, position, rotation and a local bounding box. The box is taken from the
courtyard layer when the footprint has one, otherwise from pad copper. Pad-only
boxes undersize radial parts and inductors; callers supply body overrides.

This is a screening tool. It does not replace pcbnew geometry, DRC or
connectivity checks.
"""
from __future__ import annotations
import math
import re
from dataclasses import dataclass, asdict

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text: str):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        t = m.group()
        if t == '(':
            stack.append([])
        elif t == ')':
            node = stack.pop()
            stack[-1].append(node)
        else:
            if t.startswith('"'):
                t = t[1:-1]
            stack[-1].append(t)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError('unbalanced s-expression')
    return stack[0][0]


def children(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def child(node, key, default=None):
    found = children(node, key)
    return found[0] if found else default


def _rot(x, y, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


@dataclass
class Footprint:
    ref: str
    value: str
    lib_id: str
    side: str          # 'F' or 'B'
    x: float
    y: float
    rotation: float
    width: float       # board-axis extent after rotation, mm
    height: float
    box_source: str    # 'courtyard' or 'pads'
    pads: int
    dnp: bool
    exclude_from_bom: bool

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_dict(self):
        d = asdict(self)
        d['area'] = round(self.area, 2)
        return d


def _property(fp, name):
    for p in children(fp, 'property'):
        if len(p) > 2 and p[1] == name:
            return p[2]
    return ''


def footprint_geometry(fp) -> Footprint | None:
    lib_id = fp[1]
    layer = child(fp, 'layer')[1]
    at = child(fp, 'at')
    x, y = float(at[1]), float(at[2])
    rotation = float(at[3]) if len(at) > 3 else 0.0
    attr = child(fp, 'attr', [])
    pts = []
    for g in children(fp, 'fp_line') + children(fp, 'fp_rect'):
        if child(g, 'layer')[1].endswith('CrtYd'):
            s, e = child(g, 'start'), child(g, 'end')
            pts += [(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))]
    for g in children(fp, 'fp_poly'):
        if child(g, 'layer')[1].endswith('CrtYd'):
            pts += [(float(xy[1]), float(xy[2])) for xy in children(child(g, 'pts'), 'xy')]
    source = 'courtyard'
    pads = children(fp, 'pad')
    if not pts:
        source = 'pads'
        for pad in pads:
            pa = child(pad, 'at')
            px, py = float(pa[1]), float(pa[2])
            pang = float(pa[3]) if len(pa) > 3 else 0.0
            sz = child(pad, 'size')
            w, h = float(sz[1]), float(sz[2])
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
                rx, ry = _rot(dx, dy, pang - rotation)
                pts.append((px + rx, py + ry))
    if not pts:
        return None
    w = max(p[0] for p in pts) - min(p[0] for p in pts)
    h = max(p[1] for p in pts) - min(p[1] for p in pts)
    if abs((rotation % 180) - 90) < 1e-6:
        w, h = h, w
    return Footprint(ref=_property(fp, 'Reference'), value=_property(fp, 'Value'), lib_id=lib_id,
                     side='B' if layer == 'B.Cu' else 'F', x=x, y=y, rotation=rotation,
                     width=round(w, 3), height=round(h, 3), box_source=source, pads=len(pads),
                     dnp='dnp' in attr, exclude_from_bom='exclude_from_bom' in attr)


def read_board(path):
    root = parse(open(path, encoding='utf-8').read())
    fps = [g for g in (footprint_geometry(f) for f in children(root, 'footprint')) if g]
    edge = []
    for g in children(root, 'gr_line') + children(root, 'gr_rect'):
        if child(g, 'layer')[1] == 'Edge.Cuts':
            s, e = child(g, 'start'), child(g, 'end')
            edge += [(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))]
    outline = None
    if edge:
        outline = (min(p[0] for p in edge), min(p[1] for p in edge), max(p[0] for p in edge), max(p[1] for p in edge))
    return {'footprints': fps, 'outline': outline,
            'segments': len(children(root, 'segment')), 'vias': len(children(root, 'via'))}
