"""EF_PBR record decoding (TS 31.102 §4.4.2.1)."""

import unittest

from simtrace_analyser.pbr import (looks_like_pbr, parse_pbr,
                                   parse_pbr_record)

# The records seen in the local test cards' traces.
REC_SESSION_47 = bytes.fromhex(
    'a80fc0034f3a04c1034f0108c5034fa11ea905ca034f6113'
    'aa0ac2034f4a06cb034f3d12' + 'ff' * 12)
REC_SESSION_193 = bytes.fromhex(
    'a80ac0034f3a02c5034fa104' 'aa0ac2034f4a06cb034f4f07')


class TestPbrRecord(unittest.TestCase):
    def test_session_47_record(self):
        # A8 = type 1 (ADN 4F3A/SFI 4, IAP 4F01/SFI 8, PBC 4FA1/SFI 30);
        # A9 = type 2 (EMAIL 4F61/SFI 19); AA = type 3 (EXT1 4F4A/SFI 6,
        # CCP1 4F3D/SFI 18).  The FF padding ends the record.
        parsed = parse_pbr_record(REC_SESSION_47)
        self.assertEqual(parsed['master'], '4f3a')
        types = [g['type'] for g in parsed['groups']]
        self.assertEqual(types, [1, 2, 3])
        type1 = {f['tag']: (f['fid'], f.get('sfi'))
                 for f in parsed['groups'][0]['files']}
        self.assertEqual(type1['C0'], ('4f3a', 4))
        self.assertEqual(type1['C1'], ('4f01', 8))
        self.assertEqual(type1['C5'], ('4fa1', 30))
        self.assertEqual(parsed['groups'][1]['files'][0]['name'], 'EF_EMAIL')
        self.assertEqual(parsed['groups'][2]['files'][0]['name'], 'EF_EXT1')

    def test_session_193_record(self):
        parsed = parse_pbr_record(REC_SESSION_193)
        self.assertEqual(parsed['master'], '4f3a')
        files = {f['fid']: f for g in parsed['groups'] for f in g['files']}
        self.assertEqual(files['4fa1']['name'], 'EF_PBC')
        self.assertEqual(files['4fa1']['sfi'], 4)
        self.assertEqual(files['4f4a']['name'], 'EF_EXT1')
        self.assertEqual(files['4f4f']['name'], 'EF_CCP1')

    def test_objects_without_an_sfi(self):
        # Length 2 = FID only (TS 31.102 §4.4.2.1): no SFI is declared.
        parsed = parse_pbr_record(bytes.fromhex('a808c0024f3ac5024fa1'))
        files = parsed['groups'][0]['files']
        self.assertEqual([(f['fid'], f.get('sfi')) for f in files],
                         [('4f3a', None), ('4fa1', None)])

    def test_truncated_and_unknown(self):
        # A truncated record ends parsing instead of inventing objects.
        self.assertEqual(parse_pbr_record(bytes.fromhex('a80ac0034f3a')),
                         {'groups': [], 'master': None})
        self.assertEqual(parse_pbr_record(bytes.fromhex('a804c0034f3a'))['groups'],
                         [{'type': 1, 'tag': 'A8', 'files': []}])
        # Unknown primitive tags are skipped; 'FF' padding ends the record.
        parsed = parse_pbr_record(bytes.fromhex('a809c0034f3a04d102abcd'))
        self.assertEqual([f['fid'] for f in parsed['groups'][0]['files']],
                         ['4f3a'])
        self.assertEqual(parse_pbr_record(b'\xff' * 8)['groups'], [])
        self.assertEqual(parse_pbr_record(b''),
                         {'groups': [], 'master': None})

    def test_parse_pbr_merges_records(self):
        parsed = parse_pbr([REC_SESSION_47, REC_SESSION_193])
        self.assertEqual(parsed['master'], '4f3a')
        self.assertEqual(parsed['files']['4fa1']['name'], 'EF_PBC')
        self.assertEqual(parsed['files']['4f01']['name'], 'EF_IAP')
        # A later record may add files; the first declaration is kept.
        self.assertEqual(parsed['files']['4fa1']['sfi'], 30)

    def test_shape_check(self):
        self.assertTrue(looks_like_pbr(REC_SESSION_193))
        self.assertFalse(looks_like_pbr(b''))
        self.assertFalse(looks_like_pbr(bytes.fromhex('c0034f3a')))


if __name__ == '__main__':
    unittest.main()
