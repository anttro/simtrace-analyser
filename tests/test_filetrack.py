"""Tests for the per-file tracker (counters, image, changes, SFI relations)."""

import os
import tempfile
import unittest

from simtrace_analyser.database import Database
from simtrace_analyser.filetrack import FileTracker


def sel_fid(fid, le='02'):
    """SELECT by FID (no response data yet)."""
    return f'00a4000002{fid}61{le}'


def gr(data_hex, total=None):
    """GET RESPONSE carrying *data_hex* (the FCP or the read data)."""
    n = len(data_hex) // 2 if total is None else total
    return f'00c00000{n:02x}{data_hex}9000'


def fcp(fid, sfi=None, structure=None, rec_len=None, n_rec=None, size=None):
    """A minimal FCP: file descriptor + FID (+ SFI / size TLVs).

    *structure* is the TS 102 221 Table 11.5 nibble (default: transparent,
    or linear fixed when record facts are given).
    """
    if rec_len is not None and n_rec is not None:
        b = 0x40 | 0b010 if structure is None else 0x40 | structure
        body = '8205' + f'{b:02x}21{rec_len:04x}{n_rec:02x}'
    else:
        b = 0x40 | 0b001 if structure is None else 0x40 | structure
        body = '8202' + f'{b:02x}21'
    body += '8302' + fid
    if sfi is not None:
        body += '8801' + f'{sfi << 3:02x}'
    if size is not None:
        body += '8002' + f'{size:04x}'
    return '62' + f'{len(body) // 2:02x}' + body


def read_binary(p1, p2, data_hex, sw='9000'):
    return f'00b0{p1:02x}{p2:02x}{len(data_hex) // 2:02x}{data_hex}{sw}'


def read_binary_sfi(sfi, offset, data_hex, sw='9000'):
    return f'00b0{0x80 | sfi:02x}{offset:02x}{len(data_hex) // 2:02x}{data_hex}{sw}'


def update_binary(p1, p2, data_hex, sw='9000'):
    return f'00d6{p1:02x}{p2:02x}{len(data_hex) // 2:02x}{data_hex}{sw}'


def update_binary_sfi(sfi, offset, data_hex, sw='9000'):
    return f'00d6{0x80 | sfi:02x}{offset:02x}{len(data_hex) // 2:02x}{data_hex}{sw}'


def read_record(rec, data_hex, sw='9000'):
    return f'00b2{rec:02x}0404{data_hex}{sw}'


def update_record(rec, data_hex, sw='9000'):
    return f'00dc{rec:02x}0404{data_hex}{sw}'


class TrackerCase(unittest.TestCase):
    """Runs a synthetic TPDU list through the real decode pipeline."""

    def track(self, *tpdu_hex, tracker=None):
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.addCleanup(lambda: (db._conn.close(), os.remove(tmp.name)))
        sid = db.create_session('test')
        db.insert_messages(sid, [(float(i), 'tpdu', bytes.fromhex(h), 0)
                                 for i, h in enumerate(tpdu_hex)])
        return db.track_files(sid) if tracker is None else \
            self._track_with(db, sid, tracker)

    def _track_with(self, db, sid, tracker):
        rows = db._conn.execute(
            'SELECT id, session_id, elapsed, type, data, flags FROM messages '
            'WHERE session_id=? ORDER BY elapsed, id', (sid,)).fetchall()
        db._decode_rows(rows, on_message=tracker.observe)
        return tracker.result()


class TestCountersAndRegistration(TrackerCase):
    def test_select_read_update_counters(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '9807110900106014000000'[:22]),
            update_binary(0, 0, '980711090010601495F9'),
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['counters'], {'select': 2, 'read': 1, 'update': 1})
        self.assertEqual(entry['name'], 'EF_ICCID')
        self.assertEqual(entry['size'], 10)

    def test_failed_select_does_not_register(self):
        data = self.track(sel_fid('2fe2', le='00').replace('6100', '6a82'))
        self.assertEqual(data['files'], {})
        self.assertEqual(data['timeline'], [])

    def test_reset_keeps_the_registry(self):
        from simtrace2_pysniff.gsmtap import GSMTAP_SIM_ATR
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '98' + '07' * 5),
        )
        gizmo = {'kind': 'read'}
        # An ATR (card reset) does not clear the per-file registry.
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.addCleanup(lambda: (db._conn.close(), os.remove(tmp.name)))
        sid = db.create_session('test')
        db.insert_messages(sid, [
            (0.0, 'tpdu', bytes.fromhex(sel_fid('2fe2')), 0),
            (0.5, 'tpdu', bytes.fromhex(gr(fcp('2fe2', sfi=2, size=10))), 0),
            (1.0, 'tpdu', bytes.fromhex(read_binary(0, 0, '98' + '07' * 5)), 0),
            (2.0, 'atr', bytes.fromhex('3b9f96801fc78031e073fe2117574a3382033339001e'), 0),
            (3.0, 'tpdu', bytes.fromhex(sel_fid('2fe2')), 0),
            (3.5, 'tpdu', bytes.fromhex(gr(fcp('2fe2', sfi=2, size=10))), 0),
            (4.0, 'tpdu', bytes.fromhex(read_binary(0, 0, '98' + '07' * 5)), 0),
        ])
        data = db.track_files(sid)
        self.assertEqual(data['files']['3f00/2fe2']['counters'],
                         {'select': 2, 'read': 2, 'update': 0})
        self.assertEqual(len(data['timeline']), 2)
        self.assertTrue(gizmo)

    def test_channels_merge_into_one_file(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '9807110900'),
            '01' + sel_fid('2fe2')[2:],                   # same file on channel 1
            '01' + gr(fcp('2fe2', sfi=2, size=10))[2:],
            '01' + read_binary(0, 0, '9807110900')[2:],
        )
        self.assertEqual(data['files']['3f00/2fe2']['counters']['read'], 2)
        self.assertEqual(len(data['files']), 1)


class TestImageAndChanges(TrackerCase):
    def test_read_fills_unknown_bytes_without_a_change(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '980711090010601495F9'),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['coverage']['known'], 10)
        self.assertEqual(entry['changes_total'], 0)
        self.assertEqual([i['kind'] for i in data['timeline']], ['read'])

    def test_card_change_surfaced_by_a_read(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '980711090010601495F9'),
            read_binary(0, 0, '98071109001060140000'),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['changes_total'], 1)
        change = entry['changes'][0]
        self.assertEqual(change['kind'], 'card')
        self.assertEqual(change['ranges'], [[8, 2]])
        self.assertEqual(change['before_hex'], '95f9')
        self.assertEqual(change['after_hex'], '0000')
        kinds = [i['kind'] for i in data['timeline']]
        self.assertEqual(kinds, ['read', 'card_change'])
        ref = data['timeline'][1]['change_ref']
        self.assertEqual(ref['file'], '3f00/2fe2')
        self.assertEqual(ref['idx'], 0)
        # The image follows the card.
        self.assertEqual(entry['coverage']['known'], 10)

    def test_repeating_a_read_is_not_a_change(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '980711090010601495F9'),
            read_binary(0, 0, '980711090010601495F9'),
        )
        self.assertEqual(data['files']['3f00/2fe2']['changes_total'], 0)
        self.assertEqual([i['kind'] for i in data['timeline']], ['read', 'read'])

    def test_device_change_from_an_update(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '980711090010601495F9'),
            update_binary(0, 0, '98071109001060140000'),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['changes_total'], 1)
        self.assertEqual(entry['changes'][0]['kind'], 'device')
        self.assertEqual(entry['changes'][0]['before_hex'], '95f9')
        self.assertEqual(entry['changes'][0]['after_hex'], '0000')
        update_row = [i for i in data['timeline'] if i['kind'] == 'update'][0]
        self.assertFalse(update_row['no_change'])

    def test_identical_update_is_flagged(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '980711090010601495F9'),
            update_binary(0, 0, '980711090010601495F9'),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['changes_total'], 0)
        update_row = [i for i in data['timeline'] if i['kind'] == 'update'][0]
        self.assertTrue(update_row['no_change'])

    def test_update_of_unknown_bytes_learns_without_an_event(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            update_binary(0, 0, '9807110900'),
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['coverage']['known'], 5)
        self.assertEqual(entry['changes_total'], 0)
        update_row = [i for i in data['timeline'] if i['kind'] == 'update'][0]
        self.assertFalse(update_row['no_change'])   # cannot prove a no-op


class TestRecordFiles(TrackerCase):
    def test_record_images_are_per_record(self):
        data = self.track(
            sel_fid('7fff'),
            sel_fid('6f07'), gr(fcp('6f07', rec_len=8, n_rec=3)),
            read_record(1, '0809101112131415'),
            read_record(2, '1617181920212223'),
            read_record(1, '08091011121314FF'),      # record 1 changed
        )
        entry = data['files']['7fff/6f07']
        self.assertEqual(entry['record_len'], 8)
        self.assertEqual(entry['n_records'], 3)
        self.assertEqual(entry['coverage']['known'], 16)
        self.assertEqual(entry['changes_total'], 1)
        self.assertEqual(entry['changes'][0]['ranges'], [[1, 1]])

    def test_read_data_delivered_by_get_response(self):
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            '00b000000a610a', gr('980711090010601495F9'),   # T=0 chaining
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(entry['counters']['read'], 1)
        self.assertEqual(entry['coverage']['known'], 10)
        # The timeline row points at the GET RESPONSE that carried the data.
        self.assertEqual(data['timeline'][-1]['kind'], 'read')

    def test_record_update_of_another_record(self):
        data = self.track(
            sel_fid('7fff'),
            sel_fid('6f07'), gr(fcp('6f07', rec_len=8, n_rec=3)),
            read_record(2, '1617181920212223'),
            update_record(2, '1617181920212200'),
        )
        entry = data['files']['7fff/6f07']
        self.assertEqual(entry['counters'], {'select': 1, 'read': 1, 'update': 1})
        self.assertEqual(entry['changes'][0]['kind'], 'device')
        self.assertEqual(entry['changes'][0]['ranges'], [[2, 1]])


class TestSfiResolution(TrackerCase):
    def test_normative_sfi_read(self):
        # EF_IMSI (6F07) has SFI 7 in the ADF_USIM table — no FCP needed.
        data = self.track(
            sel_fid('7fff'),                              # enter ADF_USIM
            read_binary_sfi(7, 0, '0829103254769899'),
        )
        self.assertIn('7fff/6f07', data['files'])
        entry = data['files']['7fff/6f07']
        self.assertEqual(entry['counters']['read'], 1)
        self.assertEqual(entry['coverage']['known'], 8)
        self.assertEqual(entry['sfi'], 7)

    def test_sfi_learned_from_the_fcp(self):
        data = self.track(
            sel_fid('7fff'),
            sel_fid('6f07'), gr(fcp('6f07', sfi=7, size=9)),
            read_binary_sfi(7, 0, '0829103254769899'),
        )
        self.assertEqual(list(data['files']), ['7fff/6f07'])
        self.assertEqual(data['sfi_relations']['7fff']['7'], '6f07')
        self.assertEqual(data['files']['7fff/6f07']['counters'],
                         {'select': 1, 'read': 1, 'update': 0})

    def test_provisional_sfi_entry_is_merged_when_learned_later(self):
        # The SFI access comes first (unknown relation), the SELECT with the
        # FCP afterwards — one file, one image, one counter set.
        data = self.track(
            sel_fid('7fff'),                             # enter ADF_USIM
            read_binary_sfi(7, 0, '08291032'),       # SFI 7: resolved by the
            read_binary_sfi(7, 4, '54769899AA'),     # normative USIM table
            sel_fid('6f07'), gr(fcp('6f07', sfi=7, size=9)),
            read_binary_sfi(7, 9, ''),
        )
        self.assertEqual(list(data['files']), ['7fff/6f07'])
        entry = data['files']['7fff/6f07']
        self.assertEqual(entry['counters']['read'], 2)
        self.assertEqual(entry['coverage']['known'], 9)
        self.assertEqual(entry['changes_total'], 0)
        self.assertTrue(all(i['file']['key'] == '7fff/6f07'
                            for i in data['timeline']))

    def test_provisional_merge_for_an_unknown_table(self):
        # An AID-DF has no normative table: the SFI read stays provisional
        # until the file's FCP teaches the relation.
        adf = '00a4040009a00000015141434c009000'        # SELECT by AID
        data = self.track(
            adf,
            read_binary_sfi(3, 0, 'AABBCCDD'),
            sel_fid('4f09'), gr(fcp('4f09', sfi=3, size=4)),
            read_binary_sfi(3, 0, 'AABBCCDD'),
        )
        keys = list(data['files'])
        self.assertEqual(len(keys), 1)
        self.assertIn('aid:a00000015141434c00', keys[0])
        entry = data['files'][keys[0]]
        self.assertEqual(entry['counters'], {'select': 1, 'read': 2, 'update': 0})
        self.assertEqual(entry['coverage']['known'], 4)
        self.assertEqual(entry['changes_total'], 0)

    def test_unresolvable_sfi_stays_provisional(self):
        data = self.track(
            read_binary_sfi(20, 0, 'AABB'),          # SFI 20: not in the MF table
        )
        self.assertEqual(list(data['files']), ['3f00/SFI:20'])
        self.assertEqual(data['files']['3f00/SFI:20']['counters']['read'], 1)
        self.assertEqual(data['files']['3f00/SFI:20']['coverage']['known'], 2)


class TestCapsAndLabels(TrackerCase):
    def test_image_cap_freezes_the_file(self):
        tracker = FileTracker(image_cap=8)
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=10)),
            read_binary(0, 0, '9807110900'),
            read_binary(5, 0, '10601495F9'),
            tracker=tracker,
        )
        entry = data['files']['3f00/2fe2']
        self.assertTrue(entry['image_truncated'])
        self.assertEqual(entry['coverage']['known'], 5)
        self.assertEqual(entry['counters']['read'], 2)   # counters keep going

    def test_event_cap_keeps_counting(self):
        tracker = FileTracker(events_cap=1)
        data = self.track(
            sel_fid('2fe2'), gr(fcp('2fe2', sfi=2, size=4)),
            read_binary(0, 0, 'AABBCCDD'),
            read_binary(0, 0, 'AABBCC00'),
            read_binary(0, 0, 'AABB0000'),
            tracker=tracker,
        )
        entry = data['files']['3f00/2fe2']
        self.assertEqual(len(entry['changes']), 1)
        self.assertEqual(entry['changes_total'], 2)

    def test_ef_dir_labels_are_harvested(self):
        # EF_DIR record: application template (61) with AID (4F) + label (50).
        aid = 'A0000000871002FF49FF0589'
        label = '5553494D'                     # "USIM" in Annex A coding
        content = f'4f{len(aid) // 2:02x}{aid}' + f'50{len(label) // 2:02x}{label}'
        rec = '61' + f'{len(content) // 2:02x}' + content
        data = self.track(
            sel_fid('2f00'), gr(fcp('2f00', sfi=30, rec_len=32, n_rec=1)),
            read_record(1, rec),
        )
        self.assertEqual(data['aid_labels'], {aid: 'USIM'})

    def test_unattributed_operations_are_skipped(self):
        # A read with no selection and no SFI has no file to attribute.
        data = self.track(read_binary(0, 0, 'AABBCCDD'))
        self.assertEqual(data['files'], {})
        self.assertEqual(data['timeline'], [])


class TestEndpoint(unittest.TestCase):
    def test_session_files_endpoint(self):
        from simtrace_analyser.server import RequestHandler

        class Fake(RequestHandler):
            def __init__(self, db):
                self.db = db
                self._status = None
                self._json = None

            def _send_json(self, data, status=200):
                self._status = status
                self._json = data

            def _send_error(self, status, message, code=None):
                self._status = status
                self._json = {'error': message}

        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        db = Database(tmp.name)
        self.addCleanup(lambda: (db._conn.close(), os.remove(tmp.name)))
        sid = db.create_session('test')
        db.insert_messages(sid, [
            (0.0, 'tpdu', bytes.fromhex(sel_fid('2fe2')), 0),
            (0.5, 'tpdu', bytes.fromhex(gr(fcp('2fe2', sfi=2, size=10))), 0),
            (1.0, 'tpdu', bytes.fromhex(read_binary(0, 0, '980711090010601495F9')), 0),
        ])
        h = Fake(db)
        h._handle_session_files(sid)
        self.assertEqual(h._status, 200)
        self.assertEqual(h._json['timeline_total'], 1)
        self.assertIn('3f00/2fe2', h._json['files'])
        # Unknown session → 404.
        h2 = Fake(db)
        h2._handle_session_files(99999)
        self.assertEqual(h2._status, 404)


if __name__ == '__main__':
    unittest.main()
