"""Read-only draft resource audit, not a complete pinmux solver or release signoff.

Exit 0: explicitly requested input-structure check passed.
Exit 2: default qualification gate blocked, or malformed input.
No GPIO is assigned or inferred from a connector terminal by this tool.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r'P[A-K](?:[0-9]|1[0-5])\Z')
TIMER = re.compile(r'(TIM\d+)_CH([1-4])\Z')
TIMER_BANK = re.compile(r'(TIM\d+)(?:_|$)')
FIELDS = {'function', 'stm32_pin', 'mcu_resource', 'status', 'notes'}


def audit(rows: list[dict], connector_rows: list[dict], contract: dict) -> dict:
    errors = []
    findings = []

    def add(code, category, detail, *, functions=(), source='project_requirements'):
        findings.append(dict(code=code, category=category, detail=detail,
                             functions=list(functions), source=source, blocks_release=True))

    if contract.get('schema_version') != 1 or contract.get('stage') != 'resource_audit_only':
        errors.append('Unsupported contract version or qualification stage')
    required_keys = {'target', 'decisions', 'sources', 'numbered_requirements', 'named_requirements',
                     'direct_connector_groups', 'interface_pin_facts', 'timer_reservations',
                     'qualification_evidence_required'}
    if not required_keys <= contract.keys():
        errors.append('Missing required contract fields')
    if errors:
        return dict(schema_version=1, structure_status='fail', release_eligible=False,
                    errors=errors, findings=findings)
    if contract['target'].get('family') != 'STM32F767xx':
        errors.append('Reviewed source facts cover STM32F767xx only')
    for fact in contract['interface_pin_facts']:
        if (fact.get('source') not in contract['sources'] or
                fact.get('decision') not in contract['decisions'] or
                not fact.get('pins') or any(not PIN.fullmatch(p) for p in fact['pins'])):
            errors.append('Invalid interface fact or source reference')
    by_name = {}
    by_pin = defaultdict(list)
    by_timer_channel = defaultdict(list)
    by_timer = defaultdict(list)
    by_exti = defaultdict(list)
    if not rows:
        errors.append('Empty GPIO draft')
    for index, row in enumerate(rows, 2):
        if set(row) != FIELDS or any(not isinstance(row[k], str) for k in FIELDS):
            errors.append(f'GPIO CSV row {index}: invalid columns or missing value')
            continue
        name, pin, resource = row['function'], row['stm32_pin'], row['mcu_resource']
        if not name or not resource or name in by_name:
            errors.append(f'GPIO CSV row {index}: empty or duplicate function/resource')
            continue
        if row['status'] not in {'existing_macro', 'proposed', 'unassigned'}:
            errors.append(f'GPIO CSV row {index}: unknown status; macro names are not verification')
        if pin != 'UNASSIGNED' and not PIN.fullmatch(pin):
            errors.append(f'GPIO CSV row {index}: invalid pin token {pin!r}')
            continue
        if (pin == 'UNASSIGNED') != (row['status'] == 'unassigned'):
            errors.append(f'GPIO CSV row {index}: assignment/status mismatch')
        by_name[name] = row
        if pin == 'UNASSIGNED':
            continue
        by_pin[pin].append(name)
        match = TIMER.fullmatch(resource)
        if match:
            by_timer_channel[resource].append(name)
        bank = TIMER_BANK.match(resource)
        if bank:
            by_timer[bank[1]].append(name)
        if resource == 'GPIO_EXTI':
            by_exti[int(pin[2:])].append(name)
    for kind, allocation in [('pin', by_pin), ('timer_channel', by_timer_channel), ('exti_line', by_exti)]:
        for resource, names in sorted(allocation.items(), key=lambda v: str(v[0])):
            if len(names) > 1:
                add('RESOURCE_COLLISION', 'collision', f'{kind} {resource} is allocated more than once',
                    functions=names, source='RM0410' if kind != 'pin' else 'project_requirements')
    for timer, names in sorted(by_timer.items()):
        if timer in contract['timer_reservations']:
            add('RESERVED_TIMER', 'collision', f'{timer}: {contract["timer_reservations"][timer]}', functions=names)
        if len(names) > 1:
            add('SHARED_TIMER_TIMEBASE', 'unverified_resource',
                f'{timer} channels share counter/prescaler/auto-reload; compatible periods/modes not proved',
                functions=names, source='RM0410')

    required = set(contract['named_requirements'])
    for group in contract['numbered_requirements']:
        required.update(f'{group["prefix"]}{i}' for i in range(1, group['count'] + 1))
    connector_groups = defaultdict(set)
    if not connector_rows:
        errors.append('Empty connector requirements')
    for row in connector_rows:
        if not row.get('net') or not row.get('group'):
            errors.append('Malformed connector requirement row')
            continue
        if row['group'] in contract['direct_connector_groups']:
            required.add(row['net'])
            connector_groups[row['group']].add(row['net'])
    indirect = {}
    for name, route in contract.get('indirect_functions', {}).items():
        dependencies = route.get('required_signals', [])
        if not dependencies or route.get('source') not in contract['sources'] or not route.get('component'):
            errors.append('Invalid indirect function route: ' + name)
            continue
        if name in by_name:
            errors.append('Function has both direct and indirect owners: ' + name)
        unresolved = [n for n in dependencies if n not in by_name or by_name[n]['stm32_pin'] == 'UNASSIGNED']
        indirect[name] = dict(**route, unresolved_signals=unresolved, status='unallocated' if unresolved else 'allocated_not_qualified')
    covered_indirect = {name for name, route in indirect.items() if not route['unresolved_signals']}
    missing = sorted(required - by_name.keys() - covered_indirect)
    unassigned = sorted(name for name in required & by_name.keys() if by_name[name]['stm32_pin'] == 'UNASSIGNED')
    if missing:
        add('MISSING_FUNCTIONS', 'missing_requirement', 'Required functions absent from MCU allocation', functions=missing)
    if unassigned:
        add('UNASSIGNED_FUNCTIONS', 'unassigned_requirement', 'Explicit UNASSIGNED rows still need an implementation', functions=unassigned)

    interface_review = []
    for fact in contract['interface_pin_facts']:
        intended = fact.get('functions_by_pin', {})
        overlaps = {pin: [n for n in by_pin[pin] if n != intended.get(pin)] for pin in fact['pins'] if pin in by_pin}
        overlaps = {pin: names for pin, names in overlaps.items() if names}
        selected = contract['decisions'][fact['decision']] == fact['mode']
        interface_review.append(dict(**fact, selected=selected, overlaps=overlaps,
                                     status='conflict_if_selected' if overlaps else 'no_listed_pin_overlap_not_qualified'))
        if overlaps:
            add('INTERFACE_PIN_CONFLICT', 'collision' if selected else 'conditional_conflict',
                f'{fact["mode"]}: ' + ', '.join(f'{p}={"/".join(ns)}' for p, ns in overlaps.items()),
                functions=[n for ns in overlaps.values() for n in ns], source=fact['source'])
    if 'PC13' in by_pin:
        add('PC13_ELECTRICAL_REVIEW', 'unverified_electrical',
            'PC13 output restrictions require an external buffer/load/reset-state review; not proof of an invalid coil interface',
            functions=by_pin['PC13'], source='DS11532')
    for key, value in contract['target'].items():
        if value is None:
            add('MCU_SELECTION_OPEN', 'unverified_target', f'MCU {key} is unspecified')
    for key, value in contract['decisions'].items():
        if value is None:
            add('MODE_DECISION_OPEN', 'unverified_resource', f'{key} is undecided')
        else:
            add('MODE_SELECTION_UNREVIEWED', 'unverified_resource', f'{key}={value}: selection is not qualification evidence')
    evidence = [{"requirement": name, "status": "unverified", "blocks_release": True}
                for name in contract['qualification_evidence_required']]
    # This is deliberately an audit-only gate. Editing a CSV status or adding
    # a claimed approval in JSON cannot qualify a board without a reviewed gate.
    add('AUDIT_STAGE_ONLY', 'qualification', 'No evidence acceptance/signoff mechanism exists in this audit stage')
    count = lambda category: sum(f['category'] == category for f in findings)
    return dict(
        schema_version=1, structure_status='fail' if errors else 'pass', release_eligible=False,
        qualification_status='blocked', target=contract['target'], errors=errors,
        summary=dict(gpio_rows=len(rows), assigned_pins=len(by_pin), required_functions=len(required),
                     missing_functions=len(missing), unassigned_functions=len(unassigned),
                     collision_findings=count('collision'), conditional_conflicts=count('conditional_conflict'),
                     qualification_evidence_missing=len(evidence)),
        missing_functions=missing, unassigned_functions=unassigned, indirect_functions=indirect,
        connector_requirement_coverage={group: dict(required=len(names),
            missing=sorted(names - by_name.keys())) for group, names in sorted(connector_groups.items())},
        verification=dict(package_pad='unverified', alternate_function_numbers='unverified',
                          DMA_routes='unverified', ADC_channels='unverified', electrical='unverified',
                          reset_defaults='unverified', schematic_ERC='not_run', PCB_DRC='not_run'),
        interface_review=interface_review, findings=findings, qualification_evidence=evidence,
        sources=contract['sources'], limitations=[
            'Listed interface pin facts are partial reviewed facts, not an exhaustive MCU alternate-function database.',
            'No DMA route allocation exists; this audit does not claim to detect DMA conflicts.',
            'GPIO_TIMED/TRIGGER_INPUT/CAM_INPUT do not specify a timer/EXTI backend; their conflicts remain unverified.',
            'Connector signal coverage is not a direct-pin budget: external drivers and analog frontends remain unallocated.',
            'No fabrication, flashing, powering or hardware tests were performed.'])


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpio', type=Path, default=ROOT / 'hardware/mcu_gpio_draft.csv')
    parser.add_argument('--connectors', type=Path, default=ROOT / 'pinout/power8gdi_revA_pinout.csv')
    parser.add_argument('--contract', type=Path, default=ROOT / 'hardware/resource_contract.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--gate', choices=['structure', 'release'], default='release')
    args = parser.parse_args(argv)
    paths = {'gpio_csv': args.gpio, 'connector_csv': args.connectors, 'contract': args.contract}
    try:
        result = audit(read_csv(args.gpio), read_csv(args.connectors), json.loads(args.contract.read_text(encoding='utf-8')))
        result['inputs'] = {kind: {'name': path.name, 'canonicalization': 'UTF-8 without BOM; LF newlines',
                                  'sha256': hashlib.sha256(path.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()}
                            for kind, path in paths.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = dict(schema_version=1, structure_status='fail', release_eligible=False,
                      errors=[f'{type(exc).__name__}: {exc}'])
    payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('structure_status', 'release_eligible', 'summary', 'errors') if k in result}))
    return 0 if args.gate == 'structure' and result['structure_status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
