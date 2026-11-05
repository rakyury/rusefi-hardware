"""
CAN definition import: DBC (Vector) and CANX (ECUMaster).

CANX schema (reverse-engineered from the ADU stock stream library):

    <CANbuseXport>
      <mob id="m_name" canbusID="600" ext="0|1" canbusIF="1|2" width="8"
           shift="0"
           [type="Compound8" compoundOffset=".." compoundBitPosition=".."
            compoundEndian="be"]>
        <frame offset="0" id="frame +0" [frequency="20"]>
          <channel id="c_name" type="u8|s8|u16-le|u16-be|s16-le|s16-be"
                   byteOffset="0" [bitCount=".." bitPosition=".."]
                   [multiplier=".." divider=".." offset=".."
                    decimalPlaces=".." min=".." max=".." unit=".."]/>

- canbusID is HEX without 0x prefix; ext="1" marks 29-bit IDs.
- Frame CAN id = canbusID + (frame_offset << shift), shift defaults to 0.
- Engine value = raw * multiplier / divider + offset; decimalPlaces is the
  display decimal shift (value is fixed-point by 10^decimalPlaces).
- type="CompoundN" mobs are MULTIPLEXED single-id streams (frame offset is
  the mux value at compoundBitPosition); selectors are retained in config.

Import result (both formats):
    {"messages": [{name, bus, base_can_id, is_extended, frames, id_shift,
                   "channels": [channel dicts]}],
     "signals":  [standalone signal dicts (DBC path)],
     "skipped":  ["reason", ...]}

Bus: the importer's `bus` argument picks the dash bus every imported
stream listens on - BUS_BOTH (2, the default: frames from CAN1 or CAN2),
BUS_CAN1 (0) or BUS_CAN2 (1). bus=None keeps what the file says (CANX
canbusIF 1/2; DBC has no bus -> CAN1). The Import DBC / CANX dialog asks.

Each channel dict: {"name", "unit", "config": {...ChannelDef config...}}.
Extra display keys (unit/decimals/min/max) ride in config for round-trip
export; the binary exporter ignores unknown keys.
"""

import re
import math
import xml.etree.ElementTree as ET
from fractions import Fraction
from typing import Any, Dict, List

MAX_I16 = 32767
BUS_BOTH = 2            # models.channels.BUS_BOTH (no Qt / models import here)

_TYPE_RE = re.compile(r"^([us])(\d+)(?:-(le|be))?$")


def _scale_to_fraction(scale: float) -> tuple:
    """Float scale -> (num, den) fitting int16"""
    if not math.isfinite(scale) or abs(scale) > MAX_I16:
        raise ValueError("scale does not fit the int16 rational format")
    if scale == 0:
        return 0, 1
    frac = Fraction(scale).limit_denominator(MAX_I16)
    num, den = frac.numerator, frac.denominator
    while abs(num) > MAX_I16 or den > MAX_I16:
        frac = frac.limit_denominator(den // 2 if den > 1 else 1)
        num, den = frac.numerator, frac.denominator
        if den == 1 and abs(num) > MAX_I16:
            raise ValueError("scale does not fit the int16 rational format")
    if not math.isclose(num / den, scale, rel_tol=1e-9, abs_tol=0.0):
        raise ValueError("scale would lose precision in the int16 rational format")
    return int(num), int(den)


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)[:23]


def _num(el, name: str, default: float = 0) -> float:
    """Numeric attribute; empty/malformed values fall back to default
    (stock ADU streams contain attributes like multiplier=\"\")."""
    v = el.get(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def parse_dbc(text: str, bus: int = BUS_BOTH) -> Dict[str, Any]:
    """Parse DBC text into standalone CAN signal dicts.

    Handles:
        BO_ <id> <MsgName>: <dlc> <sender>
         SG_ <name> [mux] : <start>|<len>@<endian><sign> (scale,offset)
             [min|max] "unit" receivers
    """
    signals = []
    skipped = []
    current_msg_id = None
    current_msg_name = ""
    current_extended = False
    # per-message multiplexor selector (from the "M"-flagged signal):
    # {(msg_id, extended): (start_bit, bit_length, big_endian)}
    selectors: Dict[tuple, tuple] = {}
    # deferred m<N> multiplexed signals (need the selector, which may be
    # defined on any line of the message): list of (msg_id, mux_value, dict)
    deferred: List[tuple] = []

    bo_re = re.compile(r"^BO_\s+(\d+)\s+([A-Za-z0-9_]+)\s*:")
    sg_re = re.compile(
        r"^\s*SG_\s+([A-Za-z0-9_]+)\s*(?:([Mm]\d*)\s*)?:\s*"
        r"(\d+)\|(\d+)@([01])([+-])\s*"
        r"\(\s*([-\d.eE]+)\s*,\s*([-\d.eE]+)\s*\)"
        r'(?:\s*\[[^\]]*\])?\s*"([^"]*)"')

    for line in text.splitlines():
        m = bo_re.match(line)
        if m:
            raw_id = int(m.group(1))
            # DBC extended IDs have bit 31 set
            current_msg_id = raw_id & 0x1FFFFFFF
            current_extended = bool(raw_id & 0x80000000)
            current_msg_name = m.group(2)
            if raw_id > 0x9FFFFFFF or raw_id & 0x60000000 or (
                    not current_extended and current_msg_id > 0x7FF):
                skipped.append(f"{current_msg_name}: invalid standard/extended CAN ID")
                current_msg_id = None
            continue

        m = sg_re.match(line)
        if m and current_msg_id is not None:
            (name, mux, start_bit, length, endian, sign,
             scale, offset, unit) = m.groups()
            try:
                num, den = _scale_to_fraction(float(scale))
                offset_value = float(offset)
                if not math.isfinite(offset_value) or not offset_value.is_integer():
                    raise ValueError("fractional/nonfinite offset needs explicit fixed-point metadata")
                if not -(2**31) <= offset_value <= 2**31 - 1:
                    raise ValueError("offset is outside int32")
            except ValueError as exc:
                skipped.append(f"{name}: {exc}")
                continue
            sig = {
                "name": _sanitize(name),
                "message": current_msg_name,
                "unit": unit,
                "config": {
                    "can_id": current_msg_id,
                    "is_extended": current_extended,
                    "bus": 0 if bus is None else bus,
                    "start_bit": int(start_bit),
                    "bit_length": int(length),
                    # DBC: @1 = little-endian (Intel), @0 = big (Motorola);
                    # the same keys the channel dialog edits and
                    # models.can_effective exports
                    "endian": "little" if endian == "1" else "big",
                    "is_signed": sign == "-",
                    "mul": num,
                    "div": den,
                    "offset": int(float(offset)),
                    "timeout_ms": 500,
                    "unit": unit,
                },
            }
            big = endian == "0"
            if mux == "M":
                # the multiplexor selector: remember its position, and also
                # keep it as a normal readable signal
                selectors[(current_msg_id, current_extended)] = (int(start_bit), int(length), big)
                signals.append(sig)
            elif mux and mux[0] in "mM":
                # m<N>: valid only when the selector == N (resolved below)
                deferred.append(((current_msg_id, current_extended), int(mux[1:] or 0), sig))
            else:
                signals.append(sig)
        elif line.lstrip().startswith("SG_ "):
            skipped.append(f"Unsupported or orphan DBC signal: {line.strip()[:160]}")

    # attach the selector to each deferred multiplexed signal
    for msg_id, mux_value, sig in deferred:
        sel = selectors.get(msg_id)
        if not sel:
            skipped.append(f"{sig['name']}: multiplexed (m{mux_value}) but "
                           "no multiplexor 'M' signal in the message")
            continue
        sbit, slen, sbe = sel
        sig["config"].update(mux_enable=True, mux_sel_bit=sbit,
                             mux_sel_len=slen, mux_be=sbe, mux_value=mux_value)
        signals.append(sig)
    return {"messages": [], "signals": signals, "skipped": skipped}


def _channel_from_canx(el, warn: List[str]):
    """One <channel> element -> channel dict (message-child addressing),
    or None (appends the reason to warn)."""
    name = _sanitize(re.sub(r"^c_", "", el.get("id", "")))
    if not name:
        warn.append("channel with no id skipped")
        return None
    m = _TYPE_RE.match(el.get("type", ""))
    if not m:
        warn.append(f"{name}: unknown type '{el.get('type')}'")
        return None
    sign, bits, endian = m.group(1), int(m.group(2)), m.group(3) or "le"
    has_bits = el.get("bitCount") is not None
    # a 64-bit container is fine as long as only a <= 32-bit field of it is
    # read (MoTeC MDC: u64-be with bitCount 12); the dash's channels are int32
    if bits not in (8, 16, 32) and not (bits == 64 and has_bits):
        warn.append(f"{name}: {bits}-bit container not supported")
        return None

    byte_off = int(_num(el, "byteOffset", 0))
    cfg: Dict[str, Any] = {
        "message_id": "",             # filled by the importer UI
        "frame_offset": 0,            # filled per <frame>
        "byte_offset": byte_off,
        "data_format": f"{bits}bit",
        "endian": "big" if endian == "be" else "little",
        "is_signed": sign == "s",
        "bitfield": False, "bit_pos": 0, "bit_count": 1,
        "mul": int(_num(el, "multiplier", 1)),
        "div": max(1, int(_num(el, "divider", 1))),
        "offset": int(_num(el, "offset", 0)),
        "timeout_ms": 500,
    }

    if has_bits:
        pos = int(_num(el, "bitPosition", 0))
        cnt = max(1, int(_num(el, "bitCount", 1)))
        # ECUMaster reads (container >> bitPosition) & mask(bitCount): a
        # count running past the container (ProEFI TurboSpeed2: bitCount 32
        # in a u16-be) only has the container's bits. Without the clamp the
        # field grew past its container into the neighbouring bytes.
        if pos >= bits:
            warn.append(f"{name}: bitPosition {pos} outside its {bits}-bit container")
            return None
        cnt = min(cnt, bits - pos)
        if cnt > 32:
            warn.append(f"{name}: {cnt}-bit field does not fit a 32-bit channel")
            return None
        # bitPosition is LSB0 within the typed container; our model
        # addresses bits from a byte, so fold the byte part in.
        place = ecum_field_place(byte_off, bits, endian == "be", pos, cnt)
        if not place["exact"]:
            warn.append(f"{name}: bitfield {cnt}@{pos} has no exact "
                        "firmware equivalent (approximated)")
        cfg.update(byte_offset=place["byte_offset"], bitfield=True,
                   bit_pos=place["bit_pos"], bit_count=place["bit_count"],
                   endian=place["endian"], data_format="8bit")

    # Display metadata (round-trip + widget hints); harmless extras.
    if el.get("unit"):
        cfg["unit"] = el.get("unit")
    if el.get("decimalPlaces") is not None:
        cfg["decimals"] = int(_num(el, "decimalPlaces", 0))
    if el.get("min") is not None:
        cfg["min"] = _num(el, "min", 0)
    if el.get("max") is not None:
        cfg["max"] = _num(el, "max", 0)

    return {"name": name, "unit": el.get("unit", ""), "config": cfg}


def ecum_field_place(byte_offset: int, container_bits: int,
                     big_endian: bool, bit_pos: int, bit_count: int) -> dict:
    """ECUMaster bit addressing -> our message-child addressing.

    ECUMaster (CANX and ADU projects): `bit_pos` is LSB0 inside a typed
    container of `container_bits` starting at `byte_offset`; a big-endian
    container numbers bytes MSB first (16-bit BE: bits 8-15 = first byte).
    Ours (models.channels.can_effective): the field's LSB as (byte, bit in
    byte) plus its width and byte order; can_effective turns a big-endian
    one into its DBC @0 MSB start bit, which the firmware's Motorola walk
    (CanDecode_ExtractRaw: down to bit 0, on at bit 7 of the next byte)
    reads exactly - so every field has an exact equivalent. A field inside
    one byte is stored little-endian (the same bits either way). Returns
    {byte_offset, bit_pos, bit_count, endian, exact}; exact False only
    when bit_count ran past the container (clamped to it).
    """
    nbytes = max(1, container_bits // 8)

    def byte_of(bit: int) -> int:
        k = bit // 8
        return byte_offset + ((nbytes - 1 - k) if big_endian else k)

    top = nbytes * 8 - 1
    lo = min(max(0, bit_pos), top)
    hi = min(lo + max(1, bit_count) - 1, top)   # clamp junk to the container
    fits = lo + max(1, bit_count) - 1 <= top
    count = hi - lo + 1
    one_byte = lo // 8 == hi // 8
    return {"byte_offset": byte_of(lo), "bit_pos": lo % 8, "bit_count": count,
            "endian": "big" if big_endian and not one_byte else "little",
            "exact": fits}


def ecum_mux_selector(bit_position: int, bit_count: int,
                      big_endian: bool) -> tuple:
    """ECUMaster compound selector -> the message-child mux fields
    (mux_sel_bit, mux_sel_len, mux_be, exact). The child config keeps the
    ECUMaster position (64-bit payload numbering of the selector's
    endianness: big-endian bit 56 = bit 0 of byte 0, 60 = byte 0's top
    nibble); models.channels.can_effective converts it for the firmware."""
    n = max(1, min(8, int(bit_count)))
    pos = max(0, min(64 - n, int(bit_position)))
    return pos, n, bool(big_endian), pos == bit_position and n == bit_count


def parse_canx(text: str, bus: int = BUS_BOTH) -> Dict[str, Any]:
    """Parse an ECUMaster .canx stream into message objects + channels.
    bus: the dash bus for every mob (default both); None = the file's
    canbusIF."""
    root = ET.fromstring(text)
    messages = []
    skipped: List[str] = []

    for mob in root.iter():
        if mob.tag.split("}")[-1].lower() != "mob":
            continue
        name = _sanitize(re.sub(r"^m_", "", mob.get("id", ""))) or "canx"
        try:
            base_id = int(mob.get("canbusID", "600"), 16)
        except ValueError:
            skipped.append(f"mob '{name}': bad canbusID "
                           f"'{mob.get('canbusID')}'")
            continue
        is_ext = mob.get("ext", "0") == "1" or base_id > 0x7FF
        mob_bus = bus if bus is not None else \
            min(1, max(0, int(_num(mob, "canbusIF", 1)) - 1))

        # "Compound" mob = ONE can id whose payload carries several layouts;
        # a selector field picks which frame is live. Selector position =
        # compoundBitPosition (else byte 0), endian = compoundEndian; the
        # mux value = compoundOffset + frame.offset. Frames DON'T shift the
        # id here (id_shift stays 0) - each frame's channels bind to the
        # base id but only decode when the selector matches.
        is_compound = bool(mob.get("type")) or \
            mob.get("compoundOffset") is not None
        # selector width = N of "CompoundN" (bits), ECUMaster default
        # position = the top N bits of byte 0, big-endian 64-bit numbering
        m_n = re.match(r"(?i)compound(\d+)$", mob.get("type", ""))
        mux_len = int(m_n.group(1)) if m_n else 8
        if not 1 <= mux_len <= 8:
            mux_len = 8   # pre-2026-10 R2 exports wrote Compound<frames>
        mux_pos = int(_num(mob, "compoundBitPosition", 64 - mux_len))
        mux_be = not str(mob.get("compoundEndian", "be")).lower().startswith(
            "l")
        mux_sel_bit, mux_sel_len, mux_fw_be, _ = ecum_mux_selector(
            mux_pos, mux_len, mux_be)
        mux_base = int(_num(mob, "compoundOffset", 0))

        msg = {
            "name": name,
            "bus": mob_bus,
            "base_can_id": base_id,
            "is_extended": is_ext,
            "frames": 1 if is_compound else max(1, int(_num(mob, "width", 1))),
            "id_shift": 0 if is_compound else int(_num(mob, "shift", 0)),
            "channels": [],
        }
        for frame in mob:
            if frame.tag.split("}")[-1].lower() != "frame":
                continue
            f_off = int(_num(frame, "offset", 0))
            for ch_el in frame:
                if ch_el.tag.split("}")[-1].lower() != "channel":
                    continue
                ch = _channel_from_canx(ch_el, skipped)
                if not ch:
                    continue
                if is_compound:
                    ch["config"]["frame_offset"] = 0
                    ch["config"].update(
                        mux_enable=True, mux_sel_bit=mux_sel_bit,
                        mux_sel_len=mux_sel_len, mux_be=mux_fw_be,
                        mux_value=mux_base + f_off)
                else:
                    ch["config"]["frame_offset"] = f_off
                msg["channels"].append(ch)
        if msg["channels"]:
            messages.append(msg)
        else:
            skipped.append(f"mob '{name}': no readable channels")

    return {"messages": messages, "signals": [], "skipped": skipped}


def import_file(path: str, bus: int = BUS_BOTH) -> Dict[str, Any]:
    """Parse a .dbc or .canx file; every stream listens on `bus` (default
    both buses; None = as the file says - see the module doc).

    Returns {"messages": [...], "signals": [...], "skipped": [...]}.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if path.lower().endswith(".canx"):
        return parse_canx(text, bus)
    return parse_dbc(text, bus)


def apply_import(doc, result: Dict[str, Any]) -> tuple:
    """Add an import_file() result to a ProjectDocument: one message object
    per mob, one CAN input channel per signal (child of its message, or
    standalone for DBC/legacy). Channels whose name already exists are
    skipped. Returns (added, duplicates)."""
    existing = {c.name for c in doc.project.channels}
    added = dupes = 0

    def add_signal(sig, message_id=""):
        nonlocal added, dupes
        if sig["name"] in existing:
            dupes += 1
            return
        cfg = dict(sig["config"])
        if message_id:
            cfg["message_id"] = message_id
        doc.add_channel("can", sig["name"], "number", cfg)
        existing.add(sig["name"])
        added += 1

    for msg in result["messages"]:
        mob = doc.add_can_message(
            msg["name"], bus=msg["bus"], base_can_id=msg["base_can_id"],
            frames=msg["frames"], is_extended=msg["is_extended"],
            id_shift=msg.get("id_shift", 0))
        for sig in msg["channels"]:
            add_signal(sig, message_id=mob.id)
    for sig in result["signals"]:
        add_signal(sig)
    return added, dupes
