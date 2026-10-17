#!/usr/bin/env python3
"""Regenerate tests/data/spec_files.json (the pinned spec tables).

The APDU decoder's file/SFI dictionaries (simtrace_analyser/ef_tables.py) are
extracted from the pinned specs in ``projects/docs/uicc``.  This tool parses
the pdftotext output of those PDFs and writes the fixture that
tests/test_decode.py asserts against, so a table edit or a spec revision can
be cross-checked mechanically.

Usage::

    python tests/extract_spec_tables.py            # regenerate the fixture
    python tests/extract_spec_tables.py --check    # diff the fixture vs the tables

The parsing rules follow the specs' own layout: file clauses carry an
``Identifier: 'XXXX'`` row (possibly with a space inside the quotes, single or
double quotes) and an optional ``SFI: 'NN'`` row; a clause that only points at
another spec's definition is resolved by its file name (e.g. "For the
structure... see EFIMSDCI in TS 31.103"); the normative SFI annexes are
parsed as tables.  Everything the parser cannot attribute to the specs is
reported, never invented.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

SPECS = {
    'ts_102_221': ('ts_102221v180400p.pdf', 'ETSI TS 102 221 V18.4.0 (Annex H)'),
    'ts_31_102': ('ts_131102v181000p.pdf', '3GPP TS 31.102 V18.10.0 (4.2-4.6, Annex H, Annex L.6)'),
    'ts_31_103': ('ts_131103v180300p.pdf', '3GPP TS 31.103 V18.3.0 (4.2)'),
    'ts_51_011': ('ts_151011v041500p.pdf', '3GPP TS 51.011 V4.15.0 (10.1-10.6)'),
}
ISIM_AID = 'aid:a0000000871004'

DF_BY_NAME = {
    'PHONEBOOK': '5f3a', 'GSM-ACCESS': '5f3b', 'MEXE': '5f3c',
    'MULTIMEDIA': '5f3b', 'MMSS': '5f3c', 'MCS': '5f3d', 'V2X': '5f3e',
    'A2X': '5f3f', 'WLAN': '5f40', 'HNB': '5f50', 'GRAPHICS': '5f50',
    'SOLSA': '5f70', 'BCAST': '5f80', 'PROSE': '5f90', 'ACDC': '5fa0',
    'TV': '5fb0', '5GS': '5fc0', 'SAIP': '5fd0', 'SNPN': '5fe0',
    '5G-PROSE': '5ff0', '5GPROSE': '5ff0',
    '5MBS-UE-PRE-CONFIGURATION': '5ff1', '5MBSUECONFIG': '5ff1',
    'IRIDIUM': '5f30', 'GLOBALSTAR': '5f31', 'ICO': '5f32', 'ACES': '5f33',
    'CTS': '5f60', 'IS-41': '7f22', 'FP-CTS': '7f23',
}

SEC = re.compile(r'^\d+(?:\.\d+)*[a-z]?\s+(EF[A-Za-z0-9_ \-]+?)(?:\s*\(.*)?$')
FID = re.compile(r"""Identifier:\s*['"]([^'"]*)['"]""")
FIDS = re.compile(r"Identifier:\s*([0-9A-Fa-f]{4})\b")
SFI = re.compile(r"SFI:\s*'?([0-9A-Fa-f]{2})'?")
FID_SENT = re.compile(r"file identifier\s*'?([0-9A-Fa-f]{4})'?", re.I)
DFSEC = re.compile(r'^\d+(?:\.\d+)*\s+Contents of [Ff]iles? at the .+? level', re.I)
SFISEC = re.compile(r'^H\.(\d+)\s+List of SFI Values at the (.+?) Level', re.I)
SFIROW = re.compile(r"^\s*'([0-9A-Fa-f]{4})\s*'?\s+'([0-9A-Fa-f]{2})'")
REF = re.compile(r'see (?:clause [0-9.]+ )?\(?(EF[A-Za-z0-9_\-]+)')

# Curated: clauses that borrowed a FID from another spec's same-named file but
# whose file is actually issuer-assigned (TS 31.102 4.4.2: the phonebook files
# are declared in EF_PBR's records), and the case-only spelling variants.
DROP = {('ts_31_102', '5f3a', '6f3a'), ('ts_31_102', '5f3a', '6f4a')}
CANON = {'EF_AaeM': 'EF_AAeM', 'EF_MExE-ST': 'EF_MexE-ST',
         'EF_OPLMNwACT': 'EF_OPLMNwAcT'}
# TS 31.102 Annex L.6 clauses state their identifiers in the clause body.
ANNEX_L = {'6fe9': 'EF_CERT', '6fea': 'EF_eFRNid', '6feb': 'EF_SCCmax'}
MF_FILES = {'2f00': 'EF_DIR', '2f05': 'EF_PL', '2f06': 'EF_ARR',
            '2f07': 'EF_ENV-CLASSES', '2f08': 'EF_UMPC', '2fe2': 'EF_ICCID'}
# The DFs listed as children of their parents by the specs themselves
# (TS 31.102 4.3/4.6, TS 51.011 10.2/10.4/10.6).
CHILD_DFS = {
    '7fff': {'5f3a': 'DF_PHONEBOOK', '5f3b': 'DF_GSM_ACCESS',
             '5f3c': 'DF_MexE', '5f40': 'DF_WLAN', '5f50': 'DF_HNB',
             '5f70': 'DF_SoLSA', '5f80': 'DF_BCAST', '5f90': 'DF_ProSe',
             '5fa0': 'DF_ACDC', '5fb0': 'DF_TV', '5fc0': 'DF_5GS',
             '5fd0': 'DF_SAIP', '5fe0': 'DF_SNPN', '5ff0': 'DF_5G_ProSe',
             '5ff1': 'DF_5MBSUECONFIG'},
    '7f10': {'5f3a': 'DF_PHONEBOOK', '5f3b': 'DF_MULTIMEDIA',
             '5f3c': 'DF_MMSS', '5f3d': 'DF_MCS', '5f3e': 'DF_V2X',
             '5f3f': 'DF_A2X', '5f50': 'DF_GRAPHICS'},
    '7f20': {'5f30': 'DF_IRIDIUM', '5f31': 'DF_GLOBALSTAR', '5f32': 'DF_ICO',
             '5f33': 'DF_ACES', '5f3c': 'DF_MexE', '5f60': 'DF_CTS',
             '5f70': 'DF_SoLSA'},
}
DF_FIDS = {
    '5f30': 'DF_IRIDIUM', '5f31': 'DF_GLOBALSTAR', '5f32': 'DF_ICO',
    '5f33': 'DF_ACES', '5f3a': 'DF_PHONEBOOK', '5f3b': 'DF_GSM_ACCESS',
    '5f3c': 'DF_MexE', '5f3d': 'DF_MCS', '5f3e': 'DF_V2X', '5f3f': 'DF_A2X',
    '5f40': 'DF_WLAN', '5f50': 'DF_HNB', '5f60': 'DF_CTS', '5f70': 'DF_SoLSA',
    '5f80': 'DF_BCAST', '5f90': 'DF_ProSe', '5fa0': 'DF_ACDC',
    '5fb0': 'DF_TV', '5fc0': 'DF_5GS', '5fd0': 'DF_SAIP', '5fe0': 'DF_SNPN',
    '5ff0': 'DF_5G_ProSe', '5ff1': 'DF_5MBSUECONFIG', '7f10': 'DF_TELECOM',
    '7f20': 'DF_GSM',
}
ORDER = ['3f00', '7fff', '7f10', '7f20', '5f3a', '5f3b', '5f3c', '5f3d',
         '5f3e', '5f3f', '5f40', '5f50', '5f70', '5f90', '5fa0', '5fc0',
         '5fe0', '5ff0', '5ff1', 'aid:a0000000871004']
SFI_ORDER = ['3f00', '7fff', '5f3b', '5f3d', '5f3e', '5f3f', '5f40', '5f50',
             '5f90', '5fa0', '5fc0', '5fe0', '5ff0', 'aid:a0000000871004']


def norm_df_name(s):
    s = re.sub(r'^(DF|THE|GSM|TELECOM)[\s-]*', '', s.strip().upper(), count=1)
    return s.replace(' ', '-').replace('_', '-')


def parse_spec(path, spec):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    files = collections.defaultdict(dict)
    sfis = collections.defaultdict(dict)
    per_file_sfi = collections.defaultdict(dict)
    unresolved = {}

    def is_heading(line):
        line = line.strip()
        if '....' in line:
            return False
        return bool(SEC.match(line) or DFSEC.match(line) or SFISEC.match(line))

    cur_df = cur_sfi_df = None
    for i, raw in enumerate(lines):
        # pdftotext emits typographic quotes in some tables; normalize them.
        ln = (raw.strip().replace('\u2018', "'").replace('\u2019', "'")
              .replace('\u201c', '"').replace('\u201d', '"'))
        if '....' in ln:
            continue
        if DFSEC.match(ln):
            mm = re.search(r'at the (.+?) level', ln, re.I)
            name = norm_df_name(mm.group(1)) if mm else ''
            cur_df = DF_BY_NAME.get(name)
        if spec in ('ts_31_102', 'ts_51_011') and ln.startswith(('4.1 ', '10.1 ')) \
                and 'MF level' in ln:
            cur_df = '3f00'
        mm = SFISEC.match(ln)
        if mm:
            name = norm_df_name(mm.group(2))
            if spec == 'ts_31_103':
                cur_sfi_df = ISIM_AID
            elif name in ('USIM-ADF', 'USIM-ADF-APPLICATION-DF'):
                cur_sfi_df = '7fff'
            else:
                cur_sfi_df = DF_BY_NAME.get(name)
            if cur_sfi_df is None and spec == 'ts_102_221':
                cur_sfi_df = '3f00' if 'MF' in mm.group(2).upper() else None
        if cur_sfi_df:
            row = SFIROW.match(ln)
            if row:
                fid = row.group(1).lower()
                prev = sfis[cur_sfi_df].get(int(row.group(2), 16))
                if prev and prev != fid:
                    print(f'WARN {spec}: SFI clash {cur_sfi_df} {fid} vs {prev}',
                          file=sys.stderr)
                sfis[cur_sfi_df][int(row.group(2), 16)] = fid
        m = SEC.match(ln)
        if not (m and m.group(1).startswith('EF')):
            continue
        sec_no = ln.split()[0]
        df = cur_df
        if spec == 'ts_31_103':
            df = ISIM_AID
        elif spec == 'ts_31_102':
            if sec_no.startswith('4.2'):
                df = '7fff'
            elif sec_no.startswith('4.1'):
                df = '3f00'
            elif sec_no.startswith('4.5'):
                df = '7f10'
        elif spec == 'ts_51_011':
            if sec_no.startswith('10.3'):
                df = '7f20'
            elif sec_no.startswith('10.5'):
                df = '7f10'
            elif sec_no.startswith('10.1'):
                df = '3f00'
        fid = sfi = None
        body = []
        for line in lines[i + 1:]:
            if is_heading(line):
                break
            body.append(line)
            if fid is None:
                fm = FID.search(line) or FIDS.search(line) or FID_SENT.search(line)
                if fm:
                    cand = re.sub(r'\s', '', fm.group(1))
                    if re.fullmatch(r'[0-9A-Fa-f]{4}', cand):
                        fid = cand.lower()
            if sfi is None:
                sm = SFI.search(line)
                if sm:
                    sfi = int(sm.group(1), 16)
        name = 'EF_' + m.group(1).replace(' ', '')[2:]
        if not df or 'This EF is not used' in '\n'.join(body):
            continue
        if fid:
            prev = files[df].get(fid)
            if prev and prev != name:
                print(f'WARN {spec}: FID clash {df} {fid}: {prev} vs {name}',
                      file=sys.stderr)
            files[df][fid] = name
            if sfi is not None:
                per_file_sfi[df][fid] = sfi
        else:
            unresolved[(spec, df, name)] = REF.findall('\n'.join(body))
    return files, sfis, per_file_sfi, unresolved


def build(docs_dir):
    texts = {}
    for spec, (pdf, _) in SPECS.items():
        src = os.path.join(docs_dir, pdf)
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            subprocess.run(['pdftotext', '-layout', src, tmp.name], check=True)
            texts[spec] = tmp.name
    files = collections.defaultdict(dict)
    sfi = collections.defaultdict(dict)
    unresolved = {}
    for spec, path in texts.items():
        fl, sf, pfs, unres = parse_spec(path, spec)
        unresolved.update(unres)
        for df, entries in fl.items():
            for fid, name in entries.items():
                if (spec, df, fid) in DROP:
                    continue
                name = CANON.get(name, name)
                prev = files[df].get(fid)
                if prev and prev != name:
                    raise SystemExit(f'curation needed: {df} {fid}: '
                                     f'{prev} vs {name} ({spec})')
                files[df][fid] = name
        for df, table in sf.items():
            sfi[df].update(table)
        for df, table in pfs.items():
            for fid, val in table.items():
                if df.startswith('aid:'):
                    sfi[df].setdefault(val, fid)
    # clauses that only reference another spec's file by name
    by_name = collections.defaultdict(set)
    for entries in files.values():
        for fid, name in entries.items():
            by_name[name].add(fid)
    for (spec, df, name), refs in sorted(unresolved.items()):
        cands = by_name.get(name) or set()
        if not cands:
            for ref in refs:
                cands |= by_name.get(ref, set())
        if len(cands) == 1 and df and (spec, df, next(iter(cands))) not in DROP:
            files[df][next(iter(cands))] = name
    files['3f00'].update(MF_FILES)
    files['7fff'].update(ANNEX_L)
    for df, children in CHILD_DFS.items():
        files[df].update(children)
    return files, sfi


def fixture(files, sfi):
    return {
        'comment': ('File/SFI tables extracted from the pinned specs by '
                    'tools/extract_spec_tables.py; asserted by '
                    'tests/test_decode.py.  Regenerate when a spec revision '
                    'is pinned.'),
        'sources': {spec: meta[1] for spec, meta in SPECS.items()},
        'files': {df: dict(files[df]) for df in ORDER},
        'sfi': {df: {f'{s:02x}': fid for s, fid in sfi[df].items()}
                for df in SFI_ORDER},
        'df_fids': DF_FIDS,
        # flat-table entries that are not spec file/DF names: the MF itself
        # and the legacy 6F65 (its value was withdrawn, TS 31.102 4.2.45 NOTE 5)
        'flat_special': {'3f00': 'MF', '6f65': 'EF_RPLMNAcT'},
    }


def check(fixture_data, repo_root):
    sys.path.insert(0, repo_root)
    from simtrace_analyser import ef_tables

    bad = 0
    for df, entries in fixture_data['files'].items():
        table = ef_tables.DF_CHILDREN.get(df, {})
        for fid, name in entries.items():
            if table.get(fid) != name:
                print(f'files mismatch {df}/{fid}: fixture {name} table {table.get(fid)}')
                bad += 1
    for df, table in fixture_data['sfi'].items():
        want = {int(s, 16): fid for s, fid in table.items()}
        got = ef_tables.SFI_BY_DF.get(df, {})
        if want != got:
            print(f'sfi mismatch {df}: fixture {want} table {got}')
            bad += 1
    names = collections.defaultdict(set)
    for entries in fixture_data['files'].values():
        for fid, name in entries.items():
            names[fid].add(name)
    for fid, name in fixture_data['df_fids'].items():
        names[fid].add(name)
    for fid, name in fixture_data['flat_special'].items():
        names[fid].add(name)
    for fid, name in ef_tables.KNOWN_FIDS.items():
        if name not in names.get(fid, set()):
            print(f'flat mismatch {fid}: {name}')
            bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--docs-dir', default=os.path.join(root, '..', 'docs', 'uicc'),
                    help='directory holding the pinned spec PDFs')
    ap.add_argument('--out', default=os.path.join(root, 'tests', 'data',
                                                  'spec_files.json'))
    ap.add_argument('--check', action='store_true',
                    help='only compare the current tables with the specs')
    args = ap.parse_args()

    files, sfi = build(args.docs_dir)
    data = fixture(files, sfi)
    if args.check:
        sys.exit(1 if check(data, root) else 0)
    with open(args.out, 'w') as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    print(f'wrote {args.out}: '
          f'{sum(len(v) for v in files.values())} files, '
          f'{sum(len(v) for v in sfi.values())} SFIs')


if __name__ == '__main__':
    main()
