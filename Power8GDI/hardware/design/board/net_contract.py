"""Strict, dependency-free merge of KiCad XML netlists for the PCB builder."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


def read_netlists(paths, aliases=None):
    aliases = aliases or {}
    components, assignments, sources = {}, {}, []
    for path in map(Path, paths):
        root = ET.parse(path).getroot()
        sources.append({"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for comp in root.findall("./components/comp"):
            ref = comp.attrib["ref"]
            if ref in components:
                raise ValueError(f"Duplicate component reference: {ref}")
            footprint = comp.findtext("footprint", "")
            if not footprint:
                raise ValueError(f"{ref}: source component has no physical footprint")
            components[ref] = {"value": comp.findtext("value", ""), "footprint": footprint,
                               "source": path.as_posix(), "pins": {},
                               "dnp": any(x.attrib.get('name')=='dnp' for x in comp.findall('property')),
                               "exclude_from_bom": any(x.attrib.get('name')=='exclude_from_bom' for x in comp.findall('property')),
                               "exclude_from_board": any(x.attrib.get('name')=='exclude_from_board' for x in comp.findall('property'))}
        for net in root.findall("./nets/net"):
            name = aliases.get(net.attrib["name"], net.attrib["name"])
            for node in net.findall("node"):
                ref, pin = node.attrib["ref"], node.attrib["pin"]
                if ref not in components:
                    raise ValueError(f"Net {name}: missing component {ref}")
                key = (ref, pin)
                if key in assignments and assignments[key] != name:
                    raise ValueError(f"Conflicting net assignments on {ref}.{pin}")
                assignments[key] = name
                components[ref]["pins"][pin] = name
    return components, assignments, sources


def compare_pad_assignments(expected, actual):
    """Return every missing/wrong/unexpected connected pad; repeated EP pads allowed."""
    errors = []
    for key, net in sorted(expected.items()):
        if key not in actual:
            errors.append(f"missing pad {key[0]}.{key[1]} expected {net}")
        elif set(actual[key]) != {net}:
            errors.append(f"wrong net {key[0]}.{key[1]} expected {net}, got {actual[key]}")
    for key, nets in sorted(actual.items()):
        if key not in expected and any(nets):
            errors.append(f"unexpected connected pad {key[0]}.{key[1]}: {nets}")
    return errors
