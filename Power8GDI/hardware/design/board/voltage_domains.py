"""One netlist-derived isolation policy for placement, DRC and routing exports.

Targets are provisional engineering constraints, not insulation certification.
Call configure(actual_core_net) before any clearance lookup; missing/retyped
PT2001 pins cause the underlying connectivity audit to fail rather than relax.
"""
import hashlib
from pathlib import Path
import re
from audit_gdi_voltage_domains import discover
from audit_battery_voltage_domains import discover as discover_battery

_gdi=None
_source=None
# LM76003-Q1 SW follows VIN; BOOT floats above SW (datasheet Rev B 6.1).
# These receive the battery-domain target rather than the regulated-logic one.
_legacy_battery_aliases=frozenset({'PTA_+Batt_filtered','PTB_+Batt_filtered','LP5_SW','LP5_BOOT'})
_battery_aliases=None


def configure(netlist):
    global _gdi,_source,_battery_aliases
    path=Path(netlist)
    evidence=discover(path)
    battery=discover_battery(path)
    _battery_aliases=frozenset(battery)|_legacy_battery_aliases
    legacy={f'PT{bank}_{suffix}' for bank in ('A','B') for suffix in ('VBOOST','Vdrive_coil','Vdrive_shunt')}
    _gdi=frozenset(evidence)|legacy
    _source={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'discovered_switching_nets':len(evidence),'discovered_battery_domain_nets':len(battery),
             'gdi_target_mm':.6,'ignition_target_mm':2.5,'battery_target_mm':.3}
    return dict(_source)


def gdi_high_voltage_nets():
    if _gdi is None:raise RuntimeError('Voltage domains must be configured from authoritative core.net first')
    return _gdi


def battery_alias_nets():
    if _battery_aliases is None:raise RuntimeError('Voltage domains must be configured first')
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
