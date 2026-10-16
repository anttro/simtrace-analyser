"""Tests for the COMPRION 'ISO Protocol Layer' text export import."""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from simtrace_analyser.comprion import (
    CLK_HZ, ERROR_MESSAGES, ComprionError, check_comprion_text, decode_text,
    looks_like_comprion, parse_application_times, parse_comprion,
    session_start_epoch,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# A 42-byte FCP (the sample card's MF) used by the SELECT fixtures.
FCP = '62288202782183023F00A50B80017183030104A88701018A01058B032F0601C60990014083010183010A'


def meta_lines(session='2026-10-16 12h15m53s_AM_Test', comment='Test phone'):
    return [
        '\t\t\t\t\t\t\t16.10.2026 15:10',
        'ISO Protocol Layer',
        '\t\tConfiguration',
        '\t\tUser:\t\tTest',
        f'\t\tSession Name:\t\t{session}',
        '\t\tWorking directory:\t\tC:\\COMPRION Session Files\\' + session,
        '\t\tSerial Number:\t\t31108',
        f'\t\tComment:\t\t{comment}',
        '\u00a9 COMPRION 2026',
        '#\tSequence\tDir\tDescription\tValue\tDelay\tMeaning',
    ]


# A self-consistent 22-byte ATR (TS 3B, T0 9F -> 15 historical bytes, TA1 96).
ATR_ROWS = [
    ('<', 'TS', '3B'), ('<', 'T0', '9F', '54,00 etu'), ('<', 'TA1', '96', '12,00 etu'),
    ('<', 'TD1', '80'), ('<', 'TD2', '1F'), ('<', 'TA3', 'C7'),
] + [('<', f'T{i}', b) for i, b in enumerate(
    ['80', '31', 'E0', '73', 'FE', '21', '17', '57', '4A', '33', '82', '03',
     '33', '39', '00'], start=1)] + [('<', 'TCK', '1E')]


def exchange(num, seq, rows):
    """One exchange: *rows* are (dir, description, value[, delay]) tuples."""
    out = []
    for i, row in enumerate(rows):
        direction, desc, value = row[0], row[1], row[2]
        delay = row[3] if len(row) > 3 else ''
        out.append('\t'.join([
            str(num) if i == 0 else '', seq if i == 0 else '', direction, desc,
            value, delay, '']))
    return out


def apdu(num, header, incoming='', outgoing='', sw='90 00', delay='', wrap=None):
    rows = [('>', 'Header [CLA INS P1 P2]', header, delay)]
    if incoming:
        rows.append(('>', 'Incoming data', incoming))
    if outgoing:
        if wrap and 0 < wrap < len(outgoing):
            # A long data block wraps onto continuation rows (no dir/desc).
            rows.append(('<', 'Outgoing data', outgoing[:wrap]))
            rows.append(('', '', outgoing[wrap:]))
        else:
            rows.append(('<', 'Outgoing data', outgoing))
    if sw:
        rows.append(('<', 'Return code [SW1 SW2]', sw))
    return exchange(num, 'APDU', rows)


def build_trace(extra=None, delays=True, wrap_fcp=False):
    """A small synthetic protocol export: reset, ATR, PPS and four APDUs."""
    rows = meta_lines()
    rows += exchange(1, 'Cold reset', [('', 'Event', '')])
    atr_rows = [(r[0], r[1], r[2], r[3] if delays and len(r) > 3 else '')
                for r in ATR_ROWS]
    rows += exchange(2, 'ATR', atr_rows)
    rows += exchange(3, 'PPS request', [
        ('>', 'PPSS', 'FF', '51,49 etu' if delays else ''),
        ('>', 'PPS0', '10'), ('>', 'PPS1', '96'), ('>', 'PCK', '79'),
    ])
    rows += exchange(4, 'PPS response', [
        ('<', 'PPSS', 'FF', '22,50 etu' if delays else ''),
        ('<', 'PPS0', '10'), ('<', 'PPS1', '96'), ('<', 'PCK', '79'),
    ])
    # Case 4: SELECT MF with the FCP response (the command carries Lc=2).
    rows += apdu(5, '00 A4 00 04', '3F 00', FCP,
                 delay='100000,00 etu' if delays else '',
                 wrap=32 if wrap_fcp else None)
    # Case 2: READ BINARY with response data (P3 becomes the response size).
    rows += apdu(6, '00 B0 00 00', '', '980711090010601495F9',
                 delay='10000 etu' if delays else '')
    # Case 3: SELECT with command data and no response data.
    rows += apdu(7, '00 A4 08 04', '2F 05', '', '6A 82',
                 delay='1000,50 etu' if delays else '')
    # SW only.
    rows += apdu(8, '00 70 00 00', '', '', '90 00',
                 delay='100 etu' if delays else '')
    rows += exchange(9, 'Power off', [('', 'Event', '')])
    if extra:
        rows += extra
    return '\r\n'.join(rows) + '\r\n'


def rows_of(text):
    return [(t, typ, data) for t, typ, data in parse_comprion(text)['messages']]


# ── ISO Application Layer fixture (the time base) ──────────────────────

APP_BLOCKS = [
    ('(Cold Reset)', 'Event:', '10.000 s'),
    ('SELECT (MF)', 'Command:', '10.057 s'),
    ('READ BINARY (Offset 0, Len 9)', 'Command:', '11.414 s'),
    ('SELECT (2F05)', 'Command:', '11.418 s'),
    ('STATUS', 'Command:', '11.422 s'),
    ('(Power Off)', 'Event:', '1 110.559 s'),   # space thousands separator
]


def build_app_trace(session='2026-10-16 12h15m53s_AM_Test', blocks=None):
    """A synthetic ISO Application Layer export matching build_trace()."""
    rows = [
        '\t\t\t\t\t\t\t16.10.2026 14:54',
        'ISO Application Layer',
        '\t\tConfiguration',
        '\t\tUser:\t\tTest',
        f'\t\tSession Name:\t\t{session}',
        '\t\tWorking directory:\t\tC:\\COMPRION Session Files\\' + session,
        f'\t\tComment:\t\tTest phone',
        '\u00a9 COMPRION 2026',
        'Command\tField\tValue',
    ]
    for name, kind, time in (APP_BLOCKS if blocks is None else blocks):
        rows += [
            f'\t\t{name}\t{kind}\t{name}',
            '\t\tStatus:\tNormal ending of command.',
            f'\t\tTime:\t{time}',
        ]
    return '\r\n'.join(rows) + '\r\n'


class TestValidation(unittest.TestCase):
    def test_protocol_export_accepted(self):
        self.assertEqual(check_comprion_text(build_trace()), '')

    def test_application_layer_rejected(self):
        text = build_trace().replace('ISO Protocol Layer', 'ISO Application Layer')
        self.assertEqual(check_comprion_text(text), 'app_layer')
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(text)
        self.assertEqual(ctx.exception.code, 'app_layer')
        self.assertIn('ISO Application Layer', ctx.exception.message)

    def test_random_text_rejected(self):
        for text in ('', 'hello world', '#\tnot a trace\n'):
            self.assertEqual(check_comprion_text(text), 'not_comprion')
            with self.assertRaises(ComprionError) as ctx:
                parse_comprion(text)
            self.assertEqual(ctx.exception.code, 'not_comprion')

    def test_protocol_title_without_table(self):
        text = 'ISO Protocol Layer\r\n\r\nsome rows\r\n'
        self.assertEqual(check_comprion_text(text), 'unsupported_layout')
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(text)
        self.assertEqual(ctx.exception.code, 'unsupported_layout')

    def test_header_without_exchanges(self):
        text = '\r\n'.join(meta_lines()) + '\r\n'
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(text)
        self.assertEqual(ctx.exception.code, 'no_data')

    def test_looks_like_comprion(self):
        self.assertTrue(looks_like_comprion(build_trace().encode('cp1252')))
        self.assertTrue(looks_like_comprion(
            build_trace().replace('ISO Protocol Layer', 'ISO Application Layer'
                                  ).encode('cp1252')))
        self.assertFalse(looks_like_comprion(b'\x0a\x0d\x0d\x0a' + b'\x00' * 64))
        self.assertFalse(looks_like_comprion(b'hello world'))

    def test_decode_text_cp1252(self):
        raw = ('\u00a9 COMPRION 2026\r\nISO Protocol Layer\r\n').encode('cp1252')
        self.assertIn('\u00a9 COMPRION', decode_text(raw))
        self.assertIn('ISO Protocol Layer', decode_text(raw))


class TestMetadata(unittest.TestCase):
    def test_metadata_and_start(self):
        result = parse_comprion(build_trace())
        meta = result['metadata']
        self.assertEqual(meta['title'], 'ISO Protocol Layer')
        self.assertEqual(meta['user'], 'Test')
        self.assertEqual(meta['session_name'], '2026-10-16 12h15m53s_AM_Test')
        self.assertEqual(meta['comment'], 'Test phone')
        self.assertEqual(meta['serial_number'], '31108')
        self.assertEqual(meta['exported'], '16.10.2026 15:10')
        expected = datetime(2026, 10, 16, 12, 15, 53).timestamp()
        self.assertAlmostEqual(result['started'], expected, places=2)
        self.assertEqual(result['exchange_count'], 9)
        self.assertEqual(result['apdu_count'], 4)

    def test_session_start_epoch_unparsable(self):
        self.assertIsNone(session_start_epoch('whatever'))
        self.assertIsNone(session_start_epoch(''))

    def test_session_name_control_chars_normalised(self):
        # Session Name becomes the session's display name: control characters
        # are stripped, quotes are legitimate (the PWA escapes them).
        text = build_trace().replace(
            '\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test',
            '\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Ev"il\x07\x1b name')
        result = parse_comprion(text)
        name = result['metadata']['session_name']
        self.assertNotIn('\x07', name)
        self.assertNotIn('\x1b', name)
        self.assertIn('"', name)
        self.assertIsNotNone(result['started'])


class TestMessageEncoding(unittest.TestCase):
    def test_message_sequence(self):
        msgs = rows_of(build_trace())
        got = [(typ, data.hex()) for _t, typ, data in msgs]
        self.assertEqual(got, [
            ('rst', '010000'),                       # reset asserted
            ('rst', '000100'),                       # reset de-asserted
            ('atr', '3b9f96801fc78031e073fe2117574a3382033339001e'),
            ('pps', 'ff109679'),
            ('pps', 'ff109679'),
            # case 4: command (Lc=2) + fabricated 61 2a, then GET RESPONSE
            ('tpdu', '00a40004023f00612a'),
            ('tpdu', '00c000002a' + FCP.lower() + '9000'),
            # case 2: P3 = the response length
            ('tpdu', '00b000000a980711090010601495f99000'),
            # case 3: command data + the returned SW
            ('tpdu', '00a40804022f056a82'),
            # SW only
            ('tpdu', '00700000009000'),
            ('vcc', '000000'),
        ])

    def test_get_response_keeps_channel(self):
        # A logical-channel-1 SELECT must be fetched on channel 1.
        extra = apdu(10, '01 A4 00 04', '3F 00', FCP)
        msgs = rows_of(build_trace(extra=extra))
        pairs = [(data.hex()) for _t, typ, data in msgs if typ == 'tpdu']
        self.assertIn('01a40004023f00612a', pairs)
        self.assertIn('01c000002a' + FCP.lower() + '9000', pairs)

    def test_continuation_rows_join(self):
        # A long outgoing block wraps onto rows with an empty description;
        # the parser must fold them back into the element's value.
        text = build_trace(wrap_fcp=True)
        self.assertIn('\r\n\t\t\t\t' + FCP[32:], text,
                      'the fixture must actually wrap the response')
        result = parse_comprion(text)
        reference = parse_comprion(build_trace())
        self.assertEqual(result['warnings'], [])
        gr = [d for _t, typ, d in result['messages']
              if typ == 'tpdu' and d.hex().startswith('00c000002a')]
        self.assertEqual(len(gr), 1)
        self.assertEqual(gr[0].hex(), '00c000002a' + FCP.lower() + '9000')
        # The wrapped and the unwrapped export must import identically.
        self.assertEqual(gr, [d for _t, typ, d in reference['messages']
                              if typ == 'tpdu' and d.hex().startswith('00c000002a')])

    def test_monotonic_timeline(self):
        msgs = rows_of(build_trace())
        elapsed = [t for t, _typ, _d in msgs]
        self.assertEqual(elapsed, sorted(elapsed))

    def test_skips(self):
        # Unknown exchange types and unusable APDU rows are reported.
        extra = (exchange(10, 'Warm reset', [('', 'Event', '')]) +
                 apdu(11, 'Z1 Z2', '', '', '90 00') +
                 apdu(12, '00 A4 00 04', '41 42 43 44', '', '61 02'))
        result = parse_comprion(build_trace(extra=extra))
        reasons = [s['reason'] for s in result['skipped']]
        self.assertIn('unparsed header', ' '.join(reasons))
        self.assertTrue(any('unknown exchange type' in w
                            for w in result['warnings']))
        # Narrow the extended-APDU skip to the >255 case.
        big = apdu(13, '80 C2 00 00', ' '.join(['00'] * 256), '', '90 00')
        result = parse_comprion(build_trace(extra=big))
        self.assertTrue(any('extended-length' in s['reason']
                            for s in result['skipped']))

    def test_missing_return_code_warns(self):
        extra = apdu(10, '00 70 00 00', '', '', sw='')
        result = parse_comprion(build_trace(extra=extra))
        self.assertTrue(any('no return code' in w for w in result['warnings']))

    def test_odd_return_code_warns(self):
        extra = apdu(10, '00 70 00 00', '', '', sw='90')
        result = parse_comprion(build_trace(extra=extra))
        self.assertTrue(any('return code length' in w for w in result['warnings']))


class TestDelays(unittest.TestCase):
    # The ATR byte rows run at the ISO default (F=372, D=1); the ATR's TA1
    # (0x96 -> F=512, D=32) applies to the exchanges after the ATR, and the
    # PPS1 then selects the rate for the APDUs.
    R372 = 372 / CLK_HZ
    R16 = 16 / CLK_HZ
    R64 = 64 / CLK_HZ

    ATR_COST = (54 + 12) * R372      # T0 + TA1 at the default rate
    PPS_REQ = 51.49
    PPS_RSP = 22.50
    APDUS = 100000 + 10000 + 1000.5 + 100

    def test_message_times(self):
        msgs = rows_of(build_trace())
        times = [(typ, d.hex(), t) for t, typ, d in msgs]
        atr = next(t for typ, hx, t in times if typ == 'atr')
        pps = next(t for typ, hx, t in times if typ == 'pps')
        select = next(t for typ, hx, t in times
                      if typ == 'tpdu' and hx.startswith('00a4000402'))
        self.assertEqual(atr, 0.0)
        self.assertAlmostEqual(pps, self.ATR_COST + self.PPS_REQ * self.R16,
                               places=6)
        self.assertAlmostEqual(
            select, self.ATR_COST + (self.PPS_REQ + self.PPS_RSP) * self.R16 +
            100000 * self.R16, places=6)

    def test_duration(self):
        result = parse_comprion(build_trace())
        expected = (self.ATR_COST +
                    (self.PPS_REQ + self.PPS_RSP + self.APDUS) * self.R16)
        self.assertAlmostEqual(result['duration'], expected, places=6)

    def test_custom_pps_rate(self):
        # PPS1 0x94 -> F=512, D=8 (64 clocks per etu).  The card switches
        # after accepting the request, so the PPS response and the following
        # APDUs already run at the new rate.
        text = build_trace().replace('\tPPS1\t96', '\tPPS1\t94')
        result = parse_comprion(text)
        expected = (self.ATR_COST + self.PPS_REQ * self.R16 +
                    (self.PPS_RSP + self.APDUS) * self.R64)
        self.assertAlmostEqual(result['duration'], expected, places=6)

    def test_delays_absent(self):
        result = parse_comprion(build_trace(delays=False))
        self.assertEqual(result['duration'], 0.0)

    def test_bad_delay_warns(self):
        text = build_trace().replace('1000,50 etu', 'soon')
        result = parse_comprion(text)
        self.assertTrue(any('unparsed delay' in w for w in result['warnings']))

    def test_dot_decimal_delays(self):
        # The decimal separator follows the exporting machine's locale.
        text = build_trace().replace('1000,50 etu', '1000.50 etu')
        result = parse_comprion(text)
        self.assertEqual(result['warnings'], [])
        self.assertEqual(result['duration'],
                         parse_comprion(build_trace())['duration'])
        from simtrace_analyser.comprion import _parse_delay
        self.assertEqual(_parse_delay('6795.06 etu'), (6795.06, 'etu'))
        self.assertEqual(_parse_delay('6795,06 etu'), (6795.06, 'etu'))


class TestTimeBase(unittest.TestCase):
    """The optional ISO Application Layer export as the timestamp source."""

    def test_parse_application_times(self):
        blocks, meta = parse_application_times(build_app_trace())
        self.assertEqual([name for name, _t in blocks],
                         [name for name, _kind, _time in APP_BLOCKS])
        self.assertEqual([round(t, 3) for _n, t in blocks],
                         [10.0, 10.057, 11.414, 11.418, 11.422, 1110.559])
        self.assertEqual(meta['session_name'], '2026-10-16 12h15m53s_AM_Test')
        self.assertEqual(meta['title'], 'ISO Application Layer')

    def test_time_base_replaces_delays(self):
        result = parse_comprion(build_trace(), times_text=build_app_trace())
        self.assertEqual(result['time_base'], 'application-layer')
        elapsed = [m[0] for m in result['messages']]
        # reset + the untimed ATR/PPS inherit the reset's time
        self.assertEqual(elapsed[:5], [0.0, 0.0, 0.0, 0.0, 0.0])
        apdus = [m for m in result['messages'] if m[1] == 'tpdu']
        # the case-4 pair shares its exchange's wall-clock time
        self.assertEqual(apdus[0][0], 0.057)
        self.assertEqual(apdus[1][0], 0.057)
        self.assertEqual(apdus[2][0], 1.414)
        self.assertEqual(apdus[3][0], 1.418)
        self.assertEqual(apdus[4][0], 1.422)
        self.assertEqual(apdus[4][0], 1.422)
        self.assertEqual(elapsed[-1], 1100.559)          # power off
        self.assertEqual(result['duration'], 1100.559)
        expected = datetime(2026, 10, 16, 12, 15, 53).timestamp() + 10.0
        self.assertAlmostEqual(result['started'], expected, places=2)

    def test_time_base_without_delays(self):
        # With exact times the Delay column (and CLK_HZ) is irrelevant.
        result = parse_comprion(build_trace(delays=False),
                                times_text=build_app_trace())
        self.assertEqual(result['time_base'], 'application-layer')
        self.assertEqual(result['duration'], 1100.559)

    def test_time_base_session_name_mismatch(self):
        app = build_app_trace(session='2026-01-01 00h00m00s_AM_Other')
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(build_trace(), times_text=app)
        self.assertEqual(ctx.exception.code, 'session_mismatch')
        self.assertIn('different sessions', ctx.exception.message)

    def test_time_base_working_directory_fallback(self):
        # No Session Name on either side: the working directory is compared.
        stripped = '\t\tSession Name:\t\t'
        proto = build_trace().replace(
            '\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test', stripped)
        app = build_app_trace().replace(
            '\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test', stripped)
        result = parse_comprion(proto, times_text=app)
        self.assertEqual(result['time_base'], 'application-layer')
        self.assertIsNone(result['started'])       # no name -> no window
        other_dir = app.replace('C:\\COMPRION Session Files\\2026-10-16 12h15m53s_AM_Test',
                                'C:\\COMPRION Session Files\\other')
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(proto, times_text=other_dir)
        self.assertEqual(ctx.exception.code, 'session_mismatch')

    def test_time_base_unverified(self):
        proto = build_trace()
        for old in ('\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test',
                    '\t\tWorking directory:\t\tC:\\COMPRION Session Files\\2026-10-16 12h15m53s_AM_Test'):
            proto = proto.replace(old, old.split('\t\t')[1].split(':')[0] + ':\t\t')
        app = build_app_trace()
        for old in ('\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test',
                    '\t\tWorking directory:\t\tC:\\COMPRION Session Files\\2026-10-16 12h15m53s_AM_Test'):
            app = app.replace(old, old.split('\t\t')[1].split(':')[0] + ':\t\t')
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(proto, times_text=app)
        self.assertEqual(ctx.exception.code, 'time_base_unverified')

    def test_time_base_count_mismatch(self):
        fewer = build_app_trace(blocks=APP_BLOCKS[:5])
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(build_trace(), times_text=fewer)
        self.assertEqual(ctx.exception.code, 'time_base_mismatch')
        extra = build_app_trace(blocks=APP_BLOCKS[:-1] +
                                [('EXTRA', 'Command:', '1 110.500 s')] +
                                APP_BLOCKS[-1:])
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(build_trace(), times_text=extra)
        self.assertEqual(ctx.exception.code, 'time_base_mismatch')
        self.assertIn('time entries', ctx.exception.message)

    def test_time_base_unparsable(self):
        for bad in (build_trace(),                     # a protocol export
                    build_app_trace().replace('Time:', 'T1me:'),
                    build_app_trace(blocks=[('X', 'Command:', 'later')])):
            with self.assertRaises(ComprionError) as ctx:
                parse_comprion(build_trace(), times_text=bad)
            self.assertEqual(ctx.exception.code, 'times_unparsable')

    def test_time_base_suppresses_delay_warnings(self):
        # With exact times the Delay column is unused: its warnings are noise
        # (and the timeline stays exact).
        text = build_trace().replace('1000,50 etu', 'soon')
        result = parse_comprion(text, times_text=build_app_trace())
        self.assertEqual(result['warnings'], [])
        self.assertEqual(result['duration'], 1100.559)
        # Without the time base the bad delay is reported.
        self.assertTrue(any('unparsed delay' in w
                            for w in parse_comprion(text)['warnings']))

    def test_time_base_non_string(self):
        with self.assertRaises(ComprionError) as ctx:
            parse_comprion(build_trace(), times_text=123)
        self.assertEqual(ctx.exception.code, 'times_unparsable')


class TestDecodePipeline(unittest.TestCase):
    """The imported rows must decode like a wire capture through the DB."""

    def _messages(self, text):
        from simtrace_analyser.database import Database
        result = parse_comprion(text)
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.addCleanup(lambda: (db._conn.close(), os.remove(tmp.name)))
        sid = db.create_session('comprion')
        db.insert_messages(sid, [(t, typ, d, 0)
                                 for t, typ, d in result['messages']])
        return db.get_messages(sid, 0, 1000)

    def test_select_and_get_response(self):
        msgs = self._messages(build_trace())
        sels = [m for m in msgs if (m.get('decoded') or {}).get('ins_name') == 'SELECT']
        self.assertTrue(sels)
        self.assertEqual(sels[0]['decoded']['body']['hex'], '3f00')
        gr = [m for m in msgs
              if (m.get('decoded') or {}).get('ins_name') == 'GET RESPONSE'
              and (m['decoded'] or {}).get('response_for')]
        self.assertTrue(gr, 'the GET RESPONSE must resolve to its SELECT')
        self.assertEqual(gr[0]['decoded']['response_for'], 'SELECT')
        self.assertTrue(gr[0]['decoded']['response']['file_descriptor'])

    def test_read_binary_file_decode(self):
        msgs = self._messages(build_trace())
        reads = [m for m in msgs
                 if (m.get('decoded') or {}).get('ins_name') == 'READ BINARY'
                 and (m['decoded'] or {}).get('body')]
        self.assertTrue(reads)
        self.assertEqual(reads[0]['decoded']['body']['hex'], '980711090010601495f9')

    def test_no_length_mismatches(self):
        msgs = self._messages(build_trace())
        bad = [m for m in msgs
               if (m.get('decoded') or {}).get('length_mismatch')]
        self.assertEqual(bad, [])


class TestFrontendDrift(unittest.TestCase):
    def test_error_texts_are_mirrored_in_the_pwa(self):
        src = (REPO_ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
        for code, message in ERROR_MESSAGES.items():
            with self.subTest(code=code):
                self.assertIn(message, src,
                              f'PWA IMPORT_ERROR_KEYS lacks the {code} text')


class TestImportEndpoint(unittest.TestCase):
    def _handler(self, body):
        from simtrace_analyser.server import RequestHandler
        from simtrace_analyser.database import Database

        class Fake(RequestHandler):
            def __init__(self, body, db):
                self.db = db
                self._body = body
                self._status = None
                self._json = None

            def _read_body(self):
                return self._body

            def _send_json(self, data, status=200):
                self._status = status
                self._json = data

            def _send_error(self, status, message, code=None):
                self._status = status
                self._json = {'error': message}
                if code:
                    self._json['code'] = code

        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.addCleanup(lambda: (db._conn.close(), os.remove(tmp.name)))
        return Fake(body, db)

    def test_import_creates_session(self):
        h = self._handler(build_trace().encode('cp1252'))
        h._handle_import_session({'format': ['comprion'], 'name': ['uploaded']})
        self.assertEqual(h._status, 200)
        self.assertEqual(h._json['format'], 'comprion')
        self.assertEqual(h._json['name'], '2026-10-16 12h15m53s_AM_Test')
        self.assertEqual(h._json['message_count'], 11)
        session = h.db.get_session(h._json['session_id'])
        self.assertEqual(session['mode'], 'comprion')
        self.assertEqual(session['name'], '2026-10-16 12h15m53s_AM_Test')

    def test_import_session_window(self):
        h = self._handler(build_trace().encode('cp1252'))
        h._handle_import_session({'format': ['comprion']})
        session = h.db.get_session(h._json['session_id'])
        started = datetime.fromisoformat(session['started'])
        ended = datetime.fromisoformat(session['ended'])
        self.assertEqual(started, datetime(2026, 10, 16, 12, 15, 53))
        self.assertGreater((ended - started).total_seconds(), 0)

    def test_import_without_session_name_uses_upload_name(self):
        text = build_trace().replace('\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Test',
                                     '\t\tSession Name:\t\t')
        h = self._handler(text.encode('cp1252'))
        h._handle_import_session({'format': ['comprion'], 'name': ['my trace']})
        self.assertEqual(h._json['name'], 'my trace')

    def test_app_layer_400(self):
        text = build_trace().replace('ISO Protocol Layer', 'ISO Application Layer')
        h = self._handler(text.encode('cp1252'))
        h._handle_import_session({'format': ['comprion']})
        self.assertEqual(h._status, 400)
        self.assertEqual(h._json['code'], 'app_layer')
        self.assertEqual(h.db.count_sessions(), 0)

    def test_not_comprion_400(self):
        h = self._handler(b'plain text')
        h._handle_import_session({'format': ['comprion']})
        self.assertEqual(h._status, 400)
        self.assertEqual(h._json['code'], 'not_comprion')

    def test_pcap_path_hint(self):
        # A COMPRION file dropped on the PCAP importer names the other button.
        h = self._handler(build_trace().encode('cp1252'))
        h._handle_import_session({})
        self.assertEqual(h._status, 400)
        self.assertEqual(h._json['code'], 'comprion_export')
        self.assertIn('Import COMPRION trace', h._json['error'])

    def test_unknown_format_400(self):
        h = self._handler(build_trace().encode('cp1252'))
        h._handle_import_session({'format': ['weird']})
        self.assertEqual(h._status, 400)
        self.assertIn('Unknown import format', h._json['error'])

    def test_import_with_time_base(self):
        body = json.dumps({'text': build_trace(),
                           'times_text': build_app_trace()}).encode('utf-8')
        h = self._handler(body)
        h._handle_import_session({'format': ['comprion']})
        self.assertEqual(h._status, 200)
        self.assertEqual(h._json['time_base'], 'application-layer')
        session = h.db.get_session(h._json['session_id'])
        # Session Name + the first Application Layer time (10.000 s)
        self.assertEqual(session['started'], '2026-10-16T12:16:03.000')
        self.assertEqual(session['ended'], '2026-10-16T12:34:23.559')
        # the first two messages are the reset pair at the trace start
        msgs = h.db.get_messages(h._json['session_id'], 0, 3)
        self.assertEqual([m['elapsed'] for m in msgs[:2]], [0.0, 0.0])

    def test_import_with_time_base_mismatch_400(self):
        body = json.dumps({
            'text': build_trace(),
            'times_text': build_app_trace(session='2026-01-01 00h00m00s_AM_X'),
        }).encode('utf-8')
        h = self._handler(body)
        h._handle_import_session({'format': ['comprion']})
        self.assertEqual(h._status, 400)
        self.assertEqual(h._json['code'], 'session_mismatch')
        self.assertEqual(h.db.count_sessions(), 0)

    def test_import_with_bad_times_text_400(self):
        body = json.dumps({'text': build_trace(),
                           'times_text': 5}).encode('utf-8')
        h = self._handler(body)
        h._handle_import_session({'format': ['comprion']})
        self.assertEqual(h._status, 400)
        self.assertIn('times_text', h._json['error'])

    def test_import_with_json_without_text_400(self):
        # A JSON envelope without a usable 'text' answers clearly instead of
        # being parsed as a COMPRION file.
        for payload in ({'times_text': 'x'}, {'text': 5}, {'other': 'y'}):
            h = self._handler(json.dumps(payload).encode('utf-8'))
            h._handle_import_session({'format': ['comprion']})
            self.assertEqual(h._status, 400)
            self.assertIn("'text' string", h._json['error'])
            self.assertEqual(h.db.count_sessions(), 0)


if __name__ == '__main__':
    unittest.main()
