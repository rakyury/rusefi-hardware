"""Bounded offline DBC/CANX inspection using racing_dash's parser.

No CAN adapter is instantiated, frames are not sent or decoded, and no project
is mutated. The preview is not an ECU-validatable receive configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .vendor.racing_dash.can_import import parse_dbc, parse_canx

MAX_BYTES = 2 * 1024 * 1024
MAX_SIGNALS = 2048


@dataclass(frozen=True)
class CANSignalPreview:
    name: str
    message: str
    bus: str
    can_id: str
    unit: str
    scale: str
    multiplexed: bool


@dataclass(frozen=True)
class CANPreview:
    source: str
    signals: tuple[CANSignalPreview, ...]
    warnings: tuple[str, ...]


def _row(signal, message=None):
    cfg = signal['config']
    parent = message or cfg
    bus = {0: 'CAN1', 1: 'CAN2', 2: 'CAN1 + CAN2'}[parent['bus']]
    identifier = parent.get('base_can_id', parent.get('can_id', 0))
    if message:
        shift = message['id_shift']
        frame = cfg.get('frame_offset', 0)
        if not 0 <= shift <= 28 or not 0 <= frame <= 255:
            raise ValueError('CANX frame addressing is outside the preview limits')
        identifier += frame << shift
    extended = parent.get('is_extended', False)
    if not 0 <= identifier <= (0x1FFFFFFF if extended else 0x7FF):
        raise ValueError('CAN identifier is out of range')
    scale = f"raw × {cfg['mul']}/{cfg['div']} + {cfg['offset']}"
    if 'decimals' in cfg:
        scale += f"; decimals={cfg['decimals']}"
    return CANSignalPreview(
        signal['name'], message['name'] if message else signal.get('message', ''),
        bus, f"0x{identifier:X} ({'29' if extended else '11'} bit)",
        signal.get('unit', ''), scale, cfg.get('mux_enable', False))


def load_can_preview(path: str | Path, bus: int | None = None) -> CANPreview:
    """Inspect a bounded UTF-8 file. None preserves CANX bus; DBC uses CAN1.

    CANX inherits racing_dash's tolerant defaults/clamps. Always display the
    warning; this result must not be installed as ECU configuration.
    """
    if bus is not None and (type(bus) is not int or bus not in (0, 1, 2)):
        raise ValueError('Bus must be CAN1, CAN2, both or file default')
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in ('.dbc', '.canx'):
        raise ValueError('Choose a .dbc or .canx file')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('CAN definition file exceeds 2 MiB')
    text = data.decode('utf-8-sig')
    warnings = ['PREVIEW ONLY: no project changes or CAN traffic. '
                'Signal addressing and ECU compatibility are not yet validated.']
    if suffix == '.canx':
        if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.IGNORECASE):
            raise ValueError('XML document types and entities are not supported')
        warnings.append('CANX uses racing_dash compatibility parsing: malformed '
                        'optional numbers may use defaults and bitfields may be '
                        'clamped. Review the original file before future activation.')
    try:
        result = parse_canx(text, bus) if suffix == '.canx' else parse_dbc(text, bus)
    except (ET.ParseError, OverflowError, ValueError) as exc:
        raise ValueError(f'Cannot inspect CAN definition: {exc}') from exc
    count = len(result['signals']) + sum(len(m['channels']) for m in result['messages'])
    if count > MAX_SIGNALS:
        raise ValueError('CAN definition exceeds 2048 preview signals')
    rows = [_row(signal) for signal in result['signals']]
    rows.extend(_row(signal, message) for message in result['messages']
                for signal in message['channels'])
    warnings.extend(result['skipped'])
    names = set()
    for row in rows:
        if row.name in names:
            warnings.append(f'Duplicate/sanitized signal name: {row.name}')
        names.add(row.name)
    if not rows:
        warnings.append('No supported signals found; nothing has been imported.')
    return CANPreview(path.name, tuple(rows), tuple(warnings))
