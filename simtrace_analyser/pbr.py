"""EF_PBR (Phone Book Reference file) record decoding — TS 31.102 §4.4.2.1.

The phonebook's files (ADN, IAP, ANR, PBC, …) have issuer-assigned FIDs, so
the static EF dictionary cannot name them.  The card declares them here:

* the constructed tags 'A8', 'A9' and 'AA' announce a type-1/2/3 file group
  (the first FID under 'A8' is the master EF, normally the ADN file);
* each nested primitive tag ('C0' … 'CC') names the kind of file and carries
  its FID and — when the object is three bytes long — its SFI
  (length '02' = FID, length '03' = FID + SFI);
* a record is padded with 'FF' after the last object.

The decoder is deliberately tolerant: unknown primitives are reported raw and
a truncated object ends the record (real cards pad and occasionally carry
longer, path-shaped type-3 references).
"""
import collections

# Table 4.2 — the primitive tags naming the phonebook files.
PBR_NAMES = {
    'C0': 'EF_ADN', 'C1': 'EF_IAP', 'C2': 'EF_EXT1', 'C3': 'EF_SNE',
    'C4': 'EF_ANR', 'C5': 'EF_PBC', 'C6': 'EF_GRP', 'C7': 'EF_AAS',
    'C8': 'EF_GAS', 'C9': 'EF_UID', 'CA': 'EF_EMAIL', 'CB': 'EF_CCP1',
    'CC': 'EF_PURI',
}
# Table 4.1 — the constructed tags: the file-linking type.
PBR_TYPES = {'A8': 1, 'A9': 2, 'AA': 3}


def _objects(data):
    """Iterate (tag, value) pairs; stop at the 'FF' padding or a truncation."""
    i = 0
    while i + 1 < len(data):
        tag = data[i]
        if tag == 0xFF:
            return
        length = data[i + 1]
        j = i + 2
        if length & 0x80:                       # BER long form (defensive)
            octets = length & 0x7F
            if j + octets > len(data):
                return
            length = int.from_bytes(data[j:j + octets], 'big')
            j += octets
        value = data[j:j + length]
        if len(value) < length:
            return
        yield tag, value
        i = j + length


def _files(value):
    out = []
    for tag, v in _objects(value):
        name = PBR_NAMES.get(f'{tag:02X}')
        if name is None:
            continue
        if len(v) == 2:                         # FID only
            item = {'tag': f'{tag:02X}', 'name': name, 'fid': v.hex()}
        elif len(v) == 3:                       # FID + SFI
            item = {'tag': f'{tag:02X}', 'name': name, 'fid': v[:2].hex(),
                    'sfi': v[2]}
        else:                                   # a path-shaped reference
            item = {'tag': f'{tag:02X}', 'name': name, 'path': v.hex()}
        out.append(item)
    return out


def parse_pbr_record(raw):
    """Decode one EF_PBR record into its type groups (and the master EF)."""
    if not raw:
        return {'groups': [], 'master': None}
    groups = []
    master = None
    for tag, value in _objects(raw):
        kind = PBR_TYPES.get(f'{tag:02X}')
        if kind is None:
            continue
        files = _files(value)
        groups.append({'type': kind, 'tag': f'{tag:02X}', 'files': files})
        if master is None and kind == 1 and files and 'fid' in files[0]:
            master = files[0]['fid']
    return {'groups': groups, 'master': master}


def parse_pbr(records):
    """Merge several EF_PBR records (the structure repeats per record)."""
    out = collections.OrderedDict()
    master = None
    for raw in records or []:
        parsed = parse_pbr_record(raw)
        if master is None:
            master = parsed['master']
        for group in parsed['groups']:
            for item in group['files']:
                if 'fid' not in item:
                    continue
                prev = out.setdefault(item['fid'], dict(item))
                prev.setdefault('types', [])
                if group['type'] not in prev['types']:
                    prev['types'].append(group['type'])
    return {'files': out, 'master': master}


def looks_like_pbr(raw):
    """Cheap shape check: the record starts with a constructed A8/A9/AA tag."""
    return bool(raw) and f'{raw[0]:02X}' in PBR_TYPES and len(raw) >= 4
