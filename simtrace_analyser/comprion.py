"""COMPRION trace import (the tool's 'ISO Protocol Layer' text export).

The COMPRION Device Manager exports a recorded session in two tab-separated
text files (CRLF, CP1252):

* **ISO Protocol Layer** — the byte-accurate protocol view (ATR, PPS, APDUs
  with their raw hex and return codes).  This is the import source.
* **ISO Application Layer** — a decoded view (no raw response bytes); it is
  rejected with a pointer to the Protocol Layer export.

Each protocol element carries a *Delay* in etu at the negotiated F/D (the F/D
half is exact — it comes from the ATR's TA1 and the PPS).  The card interface
clock is not part of the export, so a Delay-derived timeline measures only
**card/line activity time**: ``CLK_HZ`` merely fixes its unit (it is not a
measurement of the card clock), long host pauses between APDU bursts are
absent, and the result is therefore much shorter than the real session.  When
the matching **ISO Application Layer** export is supplied as well, its
per-exchange wall-clock times (``Time:`` rows, ms precision) are used
instead: the two files are first verified to belong to the same session
(``Session Name``, falling back to ``Working directory``) and their exchange
counts must align.

Exchanges are re-encoded into the wire-shaped TPDUs the analyser stores (the
shape the GSMTAP/sigrok sources produce): a case-4 exchange becomes the
command TPDU (data, no Le) plus a ``61 <len>`` status word and a GET RESPONSE
TPDU carrying the response data and the final SW — so command/response
pairing, FCP decoding and the GET RESPONSE filters all work as usual.
"""

import re
import time

from .decode import _fidi_dict

# Unit scale for the Delay-derived timeline: the COMPRION export states no
# clock, so this only converts the Delay column's etu into seconds (card/line
# activity time — it is NOT a measurement, and it is deliberately not fed
# into the sigrok CLK / RST line-event annotation).  Real-phone clocks
# measured in our own captures sit at 3.58-3.81 MHz (colorburst / Xiaomi).
CLK_HZ = 3_800_000

# Before the ATR/PPS the card runs at the ISO default Fi/Di.
_DEFAULT_F_DIV_D = 372.0

_TABLE_HEADER = ['#', 'Sequence', 'Dir', 'Description', 'Value', 'Delay', 'Meaning']
_LAYER_TITLES = ('ISO Protocol Layer', 'ISO Application Layer')

# '16.10.2026 15:10' (the export timestamp in the header block)
_DATE_RE = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})$')
# '6795,06 etu' / '6795.06 etu' (the decimal separator follows the exporting
# machine's locale) / '12 etu' / '1 234,56 etu'
_DELAY_RE = re.compile(r'^(\d[\d ]*)(?:[,.](\d+))?\s*([A-Za-z]+)$')
# '42.443 s' / '1 180.559 s' (space thousands separator, millisecond precision)
_SECONDS_RE = re.compile(r'^(\d[\d ]*)(?:[,.](\d+))?\s*s$')
# '2026-10-16 12h15m53s_AM_Android'
_SESSION_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})h(\d{2})m(\d{2})s')

# The exchanges the Application Layer export carries a block (and a Time) for:
# reset/power events and APDUs.  The ATR and the PPS exchange are protocol
# only, so the time base reuses the previous timestamp for them.
_TIME_BASE_SEQUENCES = ('Cold reset', 'Power off', 'APDU')

ERROR_MESSAGES = {
    'app_layer': "This is the 'ISO Application Layer' export — select the "
                 "'ISO Protocol Layer' file (it contains the raw APDU bytes).",
    'not_comprion': "Not a COMPRION export — expected the 'ISO Protocol Layer' "
                    "text file.",
    'unsupported_layout': "Unsupported COMPRION export layout (expected the "
                          "'ISO Protocol Layer' table).",
    'no_data': 'No APDU exchanges found in the COMPRION export.',
    'times_unparsable': 'No usable Time entries found in the ISO Application '
                        'Layer export.',
    'session_mismatch': 'The two files belong to different sessions — select '
                        'the ISO Application Layer export of the same session.',
    'time_base_unverified': 'Cannot verify that the two files belong to the '
                            'same session (no Session Name in either file).',
    'time_base_mismatch': 'The ISO Application Layer file does not match this '
                          'trace (different exchange count).',
}


class ComprionError(ValueError):
    """A COMPRION import failure carrying a stable machine code."""

    def __init__(self, code, detail=None):
        base = ERROR_MESSAGES.get(code, code)
        self.message = f'{base} ({detail})' if detail else base
        super().__init__(self.message)
        self.code = code


def decode_text(raw):
    """Decode raw file bytes to text.

    The exports are CP1252 (the banner's (c) is the only non-ASCII byte in a
    Protocol Layer file); UTF-8 is tried first so a re-encoded export still
    decodes, with CP1252 as the fallback.
    """
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def _cells(line):
    return [p.strip() for p in line.split('\t')]


def _layer_title(lines, limit=20):
    """The export's layer title ('ISO Protocol Layer'/'ISO Application
    Layer') from the header block, or None."""
    for line in lines[:limit]:
        cells = _cells(line)
        if cells and cells[0] in _LAYER_TITLES:
            return cells[0]
    return None


def _find_header(lines):
    """Index of the trace table's header row, or None."""
    for i, line in enumerate(lines):
        if _cells(line)[:7] == _TABLE_HEADER:
            return i
    return None


def check_comprion_text(text):
    """Classify a text file for the import validation ladder.

    Returns a stable code: '' when the file looks like an ISO Protocol Layer
    export, otherwise 'app_layer' / 'unsupported_layout' / 'not_comprion'.
    """
    lines = text.splitlines()
    title = _layer_title(lines)
    header = _find_header(lines)
    if title == 'ISO Application Layer':
        return 'app_layer'
    if header is not None:
        return ''
    if title == 'ISO Protocol Layer':
        return 'unsupported_layout'
    return 'not_comprion'


def looks_like_comprion(raw):
    """True when a raw file looks like a COMPRION export (either layer).

    Used for the 'wrong button' hint when a COMPRION text file is dropped on
    the PCAP import path.
    """
    if isinstance(raw, str):
        head = raw[:8192]
    else:
        head = decode_text(bytes(raw[:8192]))
    return check_comprion_text(head) in ('', 'app_layer', 'unsupported_layout')


def session_start_epoch(name):
    """Epoch seconds of a session name like '2026-10-16 12h15m53s_AM_Android'.

    Returns None when the name does not carry a parseable timestamp.
    """
    m = _SESSION_RE.match(name or '')
    if not m:
        return None
    year, month, day, hour, minute, sec = (int(x) for x in m.groups())
    try:
        return time.mktime((year, month, day, hour, minute, sec, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def parse_application_times(text):
    """Extract the per-exchange timestamps of an ISO Application Layer export.

    Returns ``([(block_name, seconds)], metadata)`` in file order.  Each
    ``Command:``/``Event:`` block carries exactly one ``Time:`` row (the
    session-relative wall-clock time of that exchange).  Raises
    :class:`ComprionError` ('times_unparsable') when no usable entries are
    found.
    """
    lines = text.splitlines()
    cut = len(lines)
    for i, line in enumerate(lines):
        cells = _cells(line)
        if 'Command' in cells and 'Field' in cells and 'Value' in cells:
            cut = i
            break
    meta = _parse_metadata(lines[:cut])
    blocks = []
    for line in lines[cut + 1:]:
        nonempty = [c for c in _cells(line) if c]
        if not nonempty:
            continue
        if len(nonempty) >= 2 and nonempty[1] in ('Command:', 'Event:'):
            blocks.append([nonempty[0], None])
            continue
        if (nonempty[0] == 'Time:' and blocks and blocks[-1][1] is None
                and len(nonempty) > 1):
            blocks[-1][1] = _parse_seconds(nonempty[1])
    missing = [name for name, t in blocks if t is None]
    if not blocks or missing:
        raise ComprionError(
            'times_unparsable',
            f'{len(blocks) - len(missing)}/{len(blocks)} blocks carry a Time')
    times = [t for _name, t in blocks]
    if times != sorted(times):
        raise ComprionError('times_unparsable', 'timestamps are not monotonic')
    return [(name, t) for name, t in blocks], meta


def _verify_time_base(meta, times_meta):
    """Refuse an Application Layer file that is not from the same session.

    The two exports of one session share the *Session Name* (and the working
    directory); the export timestamps differ and are not compared.
    """
    proto_name = (meta.get('session_name') or '').strip()
    app_name = (times_meta.get('session_name') or '').strip()
    if proto_name and app_name:
        if proto_name != app_name:
            raise ComprionError('session_mismatch',
                                f"'{proto_name}' vs '{app_name}'")
        return
    proto_dir = (meta.get('working_directory') or '').strip()
    app_dir = (times_meta.get('working_directory') or '').strip()
    if proto_dir and app_dir:
        if proto_dir != app_dir:
            raise ComprionError('session_mismatch',
                                f"'{proto_dir}' vs '{app_dir}'")
        return
    raise ComprionError('time_base_unverified')


# Session Name fields become the session's display name, so control
# characters are normalised away (quotes are legitimate and are escaped by
# the PWA when rendering).
_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]+')


def _clean_text(value, limit=200):
    text = _CONTROL_RE.sub(' ', value or '')
    text = re.sub(r' {2,}', ' ', text).strip()
    return text[:limit]


def _parse_metadata(lines):
    meta = {
        'title': '', 'user': '', 'session_name': '', 'working_directory': '',
        'serial_number': '', 'comment': '', 'exported': '',
    }
    key_map = {
        'User': 'user',
        'Session Name': 'session_name',
        'Working directory': 'working_directory',
        'Serial Number': 'serial_number',
        'Comment': 'comment',
    }
    for line in lines:
        cells = _cells(line)
        # The config rows indent the key into a later column ('', 'Configuration',
        # '', ...); values follow the key.
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        first = nonempty[0]
        if not meta['title'] and first in _LAYER_TITLES:
            meta['title'] = first
        if not meta['exported']:
            for cell in cells:
                if _DATE_RE.match(cell):
                    meta['exported'] = cell
                    break
        key = first.rstrip(':')
        if key in key_map and len(nonempty) > 1:
            meta[key_map[key]] = _clean_text(nonempty[1])
    return meta


def _hex_bytes(value):
    """Hex cell content -> bytes ('' -> b'').  Raises ValueError."""
    text = re.sub(r'\s+', '', value or '')
    if not text:
        return b''
    return bytes.fromhex(text)


def _parse_delay(value):
    """A Delay cell ('6795,06 etu') -> (amount, unit), or None."""
    m = _DELAY_RE.match(value.strip())
    if not m:
        return None
    whole = m.group(1).replace(' ', '')
    frac = m.group(2) or '0'
    return float(whole + '.' + frac), m.group(3).lower()


def _parse_seconds(value):
    """A Time cell ('1 180.559 s') -> seconds, or None."""
    m = _SECONDS_RE.match(value.strip())
    if not m:
        return None
    whole = re.sub(r'[\s\u00a0]', '', m.group(1))
    return float(whole + '.' + (m.group(2) or '0'))


def _warn_once(bucket, warnings, note):
    if note not in bucket:
        bucket.add(note)
        warnings.append(note)


def _f_div_d(fi, di, fallback):
    entry = _fidi_dict(fi, di)
    value = entry.get('f_div_d')
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return fallback


def _rate_change(exchange, f_div_d):
    """The F/D after this exchange (TA1 of an ATR, PPS1 of a PPS exchange)."""
    if exchange['seq'] == 'ATR':
        desc = 'TA1'
    elif exchange['seq'] in ('PPS request', 'PPS response'):
        desc = 'PPS1'
    else:
        return f_div_d
    for item in exchange['items']:
        if item['desc'] != desc or not item['value']:
            continue
        try:
            b = _hex_bytes(item['value'])
        except ValueError:
            return f_div_d
        if len(b) != 1:
            return f_div_d
        return _f_div_d(b[0] >> 4, b[0] & 0x0F, f_div_d)
    return f_div_d


def _item_value(items, prefix):
    """Concatenated bytes of the first item whose description starts with
    *prefix* (continuation rows were folded into it), or None when absent."""
    for item in items:
        if item['desc'].startswith(prefix):
            return _hex_bytes(item['value'])
    return None


def _push(messages, t, type_, data):
    """Append a message, clamping the timestamp so the timeline stays
    monotonic (the DB is ordered by (elapsed, id))."""
    last = messages[-1][0] if messages else 0.0
    messages.append((max(t, last), type_, data))


def _emit_exchange(exchange, messages, skipped, warn_bucket, warnings):
    seq = exchange['seq']
    items = exchange['items']

    if seq == 'Cold reset':
        # Reset card interface: RST asserted (low) then de-asserted (high),
        # the ATR follows.  Payloads per sigrok-iso7816-stream line events —
        # deliberately without the optional CLK extension: the export carries
        # no clock measurement (see CLK_HZ).
        t = items[0]['t'] if items else 0.0
        _push(messages, t, 'rst', bytes([1, 0, 0]))
        _push(messages, t, 'rst', bytes([0, 1, 0]))
        return
    if seq == 'Power off':
        t = items[0]['t'] if items else 0.0
        _push(messages, t, 'vcc', bytes([0, 0, 0]))
        return
    if seq in ('ATR', 'PPS request', 'PPS response'):
        chunks = []
        for item in items:
            if not item['value']:
                continue
            try:
                chunks.append(_hex_bytes(item['value']))
            except ValueError:
                _warn_once(warn_bucket, warnings,
                           f'{seq}: unparsed hex value {item["value"]!r} (ignored)')
        if chunks:
            _push(messages, items[0]['t'], 'atr' if seq == 'ATR' else 'pps',
                  b''.join(chunks))
        return
    if seq == 'APDU':
        _emit_apdu(exchange, messages, skipped, warn_bucket, warnings)
        return
    _warn_once(warn_bucket, warnings,
               f'unknown exchange type {seq!r} (skipped)')


def _emit_apdu(exchange, messages, skipped, warn_bucket, warnings):
    items = exchange['items']
    head_item = next((i for i in items if i['desc'].startswith('Header')), None)
    if head_item is None or not head_item['value']:
        skipped.append({'sequence': 'APDU', 'reason': 'no command header row'})
        return
    try:
        head = _hex_bytes(head_item['value'])
    except ValueError:
        skipped.append({'sequence': 'APDU',
                        'reason': f'unparsed header {head_item["value"]!r}'})
        return
    if len(head) not in (4, 5):
        skipped.append({'sequence': 'APDU',
                        'reason': f'unexpected header length {len(head)}'})
        return
    try:
        incoming = _item_value(items, 'Incoming data') or b''
        outgoing = _item_value(items, 'Outgoing data') or b''
        sw = _item_value(items, 'Return code') or b''
    except ValueError as e:
        skipped.append({'sequence': 'APDU', 'reason': f'unparsed hex value ({e})'})
        return
    if not sw:
        _warn_once(warn_bucket, warnings,
                   f'APDU {head.hex().upper()}: no return code row')
    elif len(sw) != 2:
        _warn_once(warn_bucket, warnings,
                   f'APDU {head.hex().upper()}: unexpected return code length '
                   f'{len(sw)}')
    if len(incoming) > 0xFF or len(outgoing) > 0xFF:
        # Extended-length APDUs are not part of the stored wire shape.
        skipped.append({'sequence': 'APDU',
                        'reason': 'extended-length APDU not supported'})
        return

    t1 = head_item['t']
    if len(head) == 4:
        # The export shows CLA INS P1 P2; synthesise the TPDU's P3: Lc for a
        # command with data, otherwise the response length the terminal read
        # (Le), which keeps the body/status-word split unambiguous.
        p3 = len(incoming) if incoming else (len(outgoing) if outgoing else 0)
        head = head + bytes([p3])

    if incoming and outgoing:
        # Case 4 on the wire (T=0): the command carries no Le, the card
        # answers 61 <len> and the terminal fetches with GET RESPONSE.
        # The GET RESPONSE keeps the command's logical channel (CLA low bits).
        _push(messages, t1, 'tpdu',
              head + incoming + bytes([0x61, len(outgoing)]))
        t2 = max(items[-1]['t'], t1)
        cmd = bytes([head[0] & 0x03, 0xC0, 0x00, 0x00, len(outgoing)])
        _push(messages, t2, 'tpdu', cmd + outgoing + sw)
    elif incoming:
        _push(messages, t1, 'tpdu', head + incoming + sw)
    elif outgoing:
        _push(messages, t1, 'tpdu', head + outgoing + sw)
    else:
        _push(messages, t1, 'tpdu', head + sw)


def parse_comprion(text, times_text=None):
    """Parse an ISO Protocol Layer export.

    *times_text* is the matching ISO Application Layer export: when given, its
    per-exchange wall-clock times replace the delay-derived timestamps (after
    verifying that both files are from the same session and that the exchange
    counts align).

    Returns a dict with the re-encoded ``messages`` (elapsed, type, data),
    the parsed metadata, the session start (epoch), ``time_base`` ('delays' or
    'application-layer') and a parse report.  Raises :class:`ComprionError`
    for a wrong/invalid file or an unusable time base.
    """
    code = check_comprion_text(text)
    if code:
        raise ComprionError(code)

    lines = text.splitlines()
    header_idx = _find_header(lines)
    meta = _parse_metadata(lines[:header_idx])

    times = None
    if times_text is not None:
        if not isinstance(times_text, str):
            raise ComprionError('times_unparsable')
        blocks, times_meta = parse_application_times(times_text)
        _verify_time_base(meta, times_meta)
        times = [t for _name, t in blocks]

    messages = []
    skipped = []
    warnings = []
    warn_bucket = set()
    f_div_d = _DEFAULT_F_DIV_D
    now = 0.0
    exchange = None
    exchange_count = 0
    apdu_count = 0
    timed_index = 0
    last_time = times[0] if times else 0.0

    def finish(ex):
        nonlocal exchange_count, apdu_count, timed_index, last_time
        exchange_count += 1
        if ex['seq'] == 'APDU':
            apdu_count += 1
        start = len(messages)
        force_t = None
        if times is not None:
            if ex['seq'] in _TIME_BASE_SEQUENCES:
                if timed_index >= len(times):
                    raise ComprionError(
                        'time_base_mismatch',
                        f'{len(times)} time entries vs more exchanges')
                last_time = times[timed_index]
                timed_index += 1
            force_t = last_time
        _emit_exchange(ex, messages, skipped, warn_bucket, warnings)
        if force_t is not None:
            # Every message of the exchange carries the exchange's wall-clock
            # time (an ATR/PPS has no Application Layer block: it keeps the
            # previous timestamp).
            for i in range(start, len(messages)):
                elapsed, msg_type, data = messages[i]
                messages[i] = (force_t, msg_type, data)
        return _rate_change(ex, f_div_d)

    for line in lines[header_idx + 1:]:
        cells = (_cells(line) + [''] * 7)[:7]
        _num, seq, direction, desc, value, delay, _meaning = cells
        if not any(cells):
            continue
        if seq:
            if exchange is not None:
                f_div_d = finish(exchange)
            exchange = {'seq': seq, 'items': []}
        if exchange is None:
            continue
        if delay and times is None:
            # With an Application Layer time base the Delay column is unused
            # (and its warnings would only be noise).
            parsed = _parse_delay(delay)
            if parsed is None:
                _warn_once(warn_bucket, warnings,
                           f'unparsed delay value {delay!r} (ignored)')
            else:
                amount, unit = parsed
                if unit != 'etu':
                    _warn_once(warn_bucket, warnings,
                               f'delay unit {unit!r} is not etu (ignored)')
                else:
                    now += amount * f_div_d / CLK_HZ
        if desc:
            exchange['items'].append({
                'dir': direction, 'desc': desc, 'value': value, 't': now})
        elif value:
            if exchange['items']:
                last = exchange['items'][-1]
                last['value'] = (last['value'] + ' ' + value).strip()
            else:
                skipped.append({'sequence': exchange['seq'],
                                'reason': 'continuation row without a base row'})
    if exchange is not None:
        finish(exchange)

    if not messages:
        raise ComprionError('no_data')

    if times is not None:
        if timed_index != len(times):
            raise ComprionError(
                'time_base_mismatch',
                f'{len(times)} time entries vs {timed_index} exchanges')
        # Rebase the wall-clock times: the first entry is the trace's start.
        base = times[0]
        messages = [(round(t - base, 6), msg_type, data)
                    for t, msg_type, data in messages]

    session_name = meta['session_name']
    started = session_start_epoch(session_name)
    if times is not None and started is not None:
        started += times[0]
    return {
        'format': 'comprion',
        'layer': meta['title'] or 'ISO Protocol Layer',
        'metadata': meta,
        'messages': messages,
        'message_count': len(messages),
        'exchange_count': exchange_count,
        'apdu_count': apdu_count,
        'duration': messages[-1][0],
        'started': started,
        'time_base': 'application-layer' if times is not None else 'delays',
        'skipped': skipped,
        'warnings': warnings,
    }
