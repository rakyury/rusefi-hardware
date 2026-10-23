"""One netlist-derived isolation policy for placement, DRC and routing exports.

Targets are provisional engineering constraints, not insulation certification.
Call configure(actual_core_net) before any clearance lookup; missing/retyped
PT2001 pins cause the underlying connectivity audit to fail rather than relax.
"""
import hashlib
from pathlib import Path
import re
from audit_gdi_voltage_domains import discover

_gdi=None
_source=None
_battery_aliases=frozenset({'PTA_+Batt_filtered','PTB_+Batt_filtered'})


def configure(netlist):
    global _gdi,_source
    path=Path(netlist)
    evidence=discover(path)
    legacy={f'PT{bank}_{suffix}' for bank in ('A','B') for suffix in ('VBOOST','Vdrive_coil','Vdrive_shunt')}
    _gdi=frozenset(evidence)|legacy
    _source={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'discovered_switching_nets':len(evidence),'gdi_target_mm':.6,'ignition_target_mm':2.5}
    return dict(_source)


def gdi_high_voltage_nets():
    if _gdi is None:raise RuntimeError('Voltage domains must be configured from authoritative core.net first')
    return _gdi


def battery_alias_nets():
    return _battery_aliases


def clearance_mm(name):
    domains=gdi_high_voltage_nets()
    if re.fullmatch(r'HARNESS_IGN[1-8]',name):return 2.5
    if name in domains:return .6
    if name.startswith('VBAT') or name in _battery_aliases:return .3
    return .2


def provenance():
    gdi_high_voltage_nets()
    return dict(_source)
