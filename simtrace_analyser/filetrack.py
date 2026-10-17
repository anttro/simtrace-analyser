"""Per-file tracking over a recorded session (the Files view's data model).

Unlike the per-channel selection state in ``database.py`` — which only answers
"what is selected right now" and is wiped by every reset — this tracker keeps a
**trace-wide registry keyed by (DF, FID)**: access counters, a sparse image of
the observed contents, and the change log.  It is built in a single pass over
the session's decoded messages (``Database.track_files``).

What is tracked
---------------

* **Counters** ``select``/``read``/``update``, successful operations only
  (``database._SUCCESS_SW1``), unaffected by card resets.
* **Image** — the bytes we believe the file holds: reads and updates both fill
  it (transparent files by offset, record files by record number).  Only
  *observed* bytes exist; never-read regions stay unknown.
* **Changes**
  - *device* — an UPDATE (D6/DC) that modified bytes we already knew, applied
    to the image and logged at its own APDU (``no_change`` flags a provable
    no-op: every written byte was known and identical);
  - *card* — a READ whose bytes differ from the image **on bytes we already
    knew**; logged at the read that surfaced it, with the changed ranges and
    the before/after bytes for the UI's diff.  Bytes we never saw just fill the
    image (an observation, not a change).

Registration happens on a successful SELECT **or** on any successfully
attributed read/update — including SFI-addressed operations.  SFI → FID
relations come from the normative table (``decode._SFI_BY_DF``) and from every
surfaced FCI (the FCP's ``88`` tag); an SFI access that precedes its relation
gets a provisional ``(DF, 'SFI:n')`` entry which is merged into the resolved
``(DF, FID)`` entry when the relation is learned (counters, image and change
log move over — one file, one image, one change log, whatever the access
path).

Bounds: at most ``IMAGE_CAP`` observed bytes per file (the file is frozen
afterwards — comparing against a partial image would produce fake card-change
signals) and at most ``EVENTS_CAP`` change events per file (``changes_total``
keeps counting).
"""

from .database import _SUCCESS_SW1
from .decode import (DF_CHILDREN, KNOWN_FIDS, _file_name, _is_df_fid,
                     select_target_fid, selected_df_fid, selected_df_state,
                     sfi_table)

IMAGE_CAP = 64 * 1024      # observed bytes kept per file
EVENTS_CAP = 1000          # change events kept per file

_READ_INS = (0xB0, 0xB1, 0xB2)      # binary/record reads (SEARCH RECORD is not
_UPDATE_INS = (0xD6, 0xDC)          # a content read — it returns record numbers)
_GR_READ_FOR = ('READ BINARY', 'READ RECORD')


def _success(d):
    """True when the message's status word means success (incl. 61xx)."""
    sw1 = (d.get('sw') or {}).get('sw1')
    return sw1 in _SUCCESS_SW1


def _body_bytes(d):
    return bytes.fromhex((d.get('body') or {}).get('hex') or '')


def _file_label(d):
    """The display name of an operation's file (same vocabulary as the Map
    view: the EF name, the FID, or the SFI placeholder)."""
    f = d.get('file') or {}
    if f.get('ef'):
        return f['ef']
    if f.get('fid'):
        return f['fid'].upper()
    if f.get('sfi') is not None:
        return f'SFI {f["sfi"]}'
    return None


def _file_path(df, fid, name, aid_labels=None, df_path=None):
    """A human-readable path for a tracked file: the DF chain (named when
    known), the EF and the FID — e.g. ``MF/EF_ICCID (2FE2)``,
    ``ADF/EF_IMSI (6F07)``, ``DF_TELECOM/DF_PHONEBOOK/4FA1``,
    ``AID A00000015141434C00/4F09``.  Without *df_path* the current DF is
    named alone (the previous behaviour)."""
    ef = (DF_CHILDREN.get(df, {}) or {}).get(fid) or name or fid.upper()
    labels = []
    for comp in df_path or []:
        if comp == '3f00' and len(df_path) > 1:
            continue                # MF is implicit in a longer path
        if comp.startswith('aid:'):
            aid = comp[4:].upper()
            label = (aid_labels or {}).get(aid)
            labels.append(f'AID {aid}' + (f' ({label})' if label else ''))
        elif comp == '7fff':
            labels.append('ADF')
        else:
            labels.append(KNOWN_FIDS.get(comp) or comp.upper())
    if not labels:
        if df.startswith('aid:'):
            aid = df[4:].upper()
            label = (aid_labels or {}).get(aid)
            labels = [f'AID {aid}' + (f' ({label})' if label else '')]
        elif df == '7fff':
            labels = ['ADF']
        else:
            labels = [KNOWN_FIDS.get(df) or df.upper()]
    df_label = '/'.join(labels)
    if ef.upper() == fid.upper():
        return f'{df_label}/{ef.upper()}'
    return f'{df_label}/{ef} ({fid.upper()})'


def _key_str(key):
    df, fid = key
    return f'{df}/{fid}'


def _parse_key(key):
    df, _sep, fid = (key or '').rpartition('/')
    return df, fid


def _apply_hex(buf, ranges, hex_str):
    """Write a concatenated hex string into *buf* at the given ranges."""
    at = 0
    for pos, length in ranges or []:
        chunk = bytes.fromhex(hex_str[at:at + length * 2])
        at += length * 2
        if len(buf) < pos + length:
            buf.extend(b'\x00' * (pos + length - len(buf)))
        buf[pos:pos + length] = chunk


def _segments(buf, mask):
    """Observed runs of the image: ``[{'offset': n, 'hex': '…'}, …]``."""
    out = []
    i = 0
    while i < len(mask):
        if not mask[i]:
            i += 1
            continue
        start = i
        while i < len(mask) and mask[i]:
            i += 1
        out.append({'offset': start, 'hex': bytes(buf[start:i]).hex()})
    return out


class _FileEntry:
    """One tracked file: counters, sparse image, change log."""

    def __init__(self, key, df, fid, name, image_cap=IMAGE_CAP, df_path=None):
        self.key = key
        self.df = df
        self.fid = fid
        self.name = name
        self.df_path = list(df_path or [])
        self.image_cap = image_cap
        self.sfi = None
        self.structure = None
        self.size = None
        self.record_len = None
        self.n_records = None
        self.counters = {'select': 0, 'read': 0, 'update': 0}
        self.changes = []
        self.changes_total = 0
        self.image_truncated = False
        # Observed contents: transparent files in one buffer indexed by the
        # byte offset; record files per record number.  The masks mark the
        # bytes that came from an observation (everything else is unknown).
        self.buf = bytearray()
        self.mask = bytearray()
        self.records = {}
        self.rec_mask = {}

    # -- image ----------------------------------------------------------

    def _tracked_bytes(self):
        return len(self.buf) + sum(len(r) for r in self.records.values())

    def apply(self, record, offset, data):
        """Apply observed bytes.

        Returns ``(diffs, observed, compared_all)``:

        * *diffs* — ``[(pos, before, after)]`` for positions whose known value
          differed (pos = the byte offset in the file, or *in the record* for
          record files);
        * *observed* — ``[(pos, len)]`` runs whose bytes were not known before
          this operation (a first observation);
        * *compared_all* — every written byte was already known (so an empty
          diff proves a no-op).
        """
        if self.image_truncated:
            return [], [], False
        if record is None:
            buf, mask, base = self.buf, self.mask, offset
            needed = base + len(data)
        else:
            buf = self.records.setdefault(record, bytearray())
            mask = self.rec_mask.setdefault(record, bytearray())
            base = 0
            needed = len(data)
        if (needed > len(buf)
                and self._tracked_bytes() + (needed - len(buf)) > self.image_cap):
            self.image_truncated = True
            return [], [], False
        if len(buf) < needed:
            buf.extend(b'\x00' * (needed - len(buf)))
            mask.extend(b'\x00' * (needed - len(mask)))
        diffs = []
        observed = []
        compared_all = True
        i = 0
        while i < len(data):
            pos = base + i
            if not mask[pos]:
                compared_all = False
                start = pos
                while i < len(data) and not mask[base + i]:
                    buf[base + i] = data[i]
                    mask[base + i] = 1
                    i += 1
                observed.append((start, i - (start - base)))
                continue
            if buf[pos] == data[i]:
                i += 1
                continue
            start = pos
            before = bytearray()
            after = bytearray()
            while i < len(data) and mask[base + i] and buf[base + i] != data[i]:
                before.append(buf[base + i])
                after.append(data[i])
                buf[base + i] = data[i]
                i += 1
            diffs.append((start, bytes(before), bytes(after)))
        return diffs, observed, compared_all

    def coverage(self):
        known = sum(self.mask) + sum(sum(m) for m in self.rec_mask.values())
        return {'known': known, 'observed': self._tracked_bytes(),
                'size': self.size}


class FileTracker:
    """Builds the per-file registry from a session's decoded messages."""

    def __init__(self, image_cap=IMAGE_CAP, events_cap=EVENTS_CAP):
        self._image_cap = image_cap
        self._events_cap = events_cap
        self.files = {}            # key -> _FileEntry
        self.timeline = []         # one item per read/update/card change
        self.sfi_relations = {}    # df -> {sfi: fid}
        self.aid_labels = {}       # AID (upper hex) -> application label
        self._index = 0
        self._pending_read = {}    # channel -> {'d', 'df'} read awaiting its data

    # -- observation ----------------------------------------------------

    def observe(self, msg, state, channel=0):
        """Observe one decoded message; *state* is the channel state before it."""
        index = self._index
        self._index += 1
        d = msg.get('decoded')
        if msg.get('type') != 'tpdu' or not d or not d.get('ins_hex'):
            return
        ins_hex = d['ins_hex']
        df = state.get('df') or '3f00'
        df_path = state.get('df_path') or [df]
        if ins_hex == 'c0':
            self._observe_get_response(d, state, channel, index, msg)
            return
        self._pending_read.pop(channel, None)
        ins = int(ins_hex, 16)
        if ins == 0xA4:
            self._observe_select(d, df, df_path)
        elif ins in _UPDATE_INS:
            self._observe_write(d, df, index, msg, df_path)
        elif ins in _READ_INS:
            self._observe_read(d, df, channel, index, msg, df_path)

    # -- file registry ---------------------------------------------------

    def _entry(self, df, fid, name=None, df_path=None):
        key = (df, fid)
        entry = self.files.get(key)
        if entry is None:
            # A file first seen via its FCP (or an operation whose decode had
            # no name) still gets its DF-scoped dictionary name.
            entry = _FileEntry(key, df, fid,
                               (name or _file_name(fid, df)) if fid else '?',
                               image_cap=self._image_cap, df_path=df_path)
            self.files[key] = entry
        elif df_path and len(df_path) > len(entry.df_path) and \
                list(df_path[:len(entry.df_path)]) == entry.df_path:
            # A fuller path learned later (e.g. the DF was entered by a path
            # selection after the first FCP-only sighting).
            entry.df_path = list(df_path)
        if name:
            placeholders = {entry.fid, entry.fid.upper(), '', '?'}
            if entry.sfi is not None:
                placeholders.add(f'SFI {entry.sfi}')
                placeholders.add(f'SFI:{entry.sfi}')
            if entry.name in placeholders:
                entry.name = name
        return entry

    def _resolve_sfi(self, df, sfi):
        rel = self.sfi_relations.get(df, {})
        if sfi in rel:
            return rel[sfi]
        return sfi_table(df).get(sfi)

    def _learn_sfi(self, df, sfi, fid, entry=None):
        self.sfi_relations.setdefault(df, {})[sfi] = fid
        if entry is not None:
            entry.sfi = sfi
        self._merge_provisional(df, sfi, fid)

    def _file_ref(self, d, df):
        """(fid-or-provisional-key, sfi) for an operation's file."""
        f = d.get('file') or {}
        sfi = f.get('sfi')
        if sfi is None:
            sfi = (d.get('p1p2') or {}).get('sfi')
        if sfi is None:
            sfi = (d.get('p2') or {}).get('sfi')
        fid = f.get('fid')
        if fid:
            return fid, sfi
        if sfi is not None:
            resolved = self._resolve_sfi(df, sfi)
            if resolved:
                self._learn_sfi(df, sfi, resolved)
                return resolved, sfi
            return f'SFI:{sfi}', sfi
        return None, None

    def _merge_provisional(self, df, sfi, fid):
        """Fold a provisional (df, 'SFI:n') entry into the resolved one."""
        provisional = self.files.get((df, f'SFI:{sfi}'))
        if provisional is None:
            return
        del self.files[(df, f'SFI:{sfi}')]
        real = self.files.get((df, fid))
        if real is None:
            provisional.key = (df, fid)
            provisional.fid = fid
            provisional.sfi = sfi
            if provisional.name == f'SFI:{sfi}':
                provisional.name = _file_name(fid, df)
            self.files[(df, fid)] = provisional
            target = provisional
        else:
            real.sfi = sfi
            for kind in ('select', 'read', 'update'):
                real.counters[kind] += provisional.counters[kind]
            _merge_image(real, provisional)
            real.changes = sorted(real.changes + provisional.changes,
                                  key=lambda c: c['index'])
            real.changes_total += provisional.changes_total
            target = real
        for item in self.timeline:
            if item.get('entry') is provisional:
                item['entry'] = target
                item['file'] = self._file_json(target)

    def _file_json(self, entry):
        return {'key': _key_str(entry.key), 'name': entry.name,
                'fid': entry.fid, 'df': entry.df, 'sfi': entry.sfi}

    def _push(self, kind, entry, index, msg, **extra):
        item = {'kind': kind, 'entry': entry, 'index': index,
                'msg_id': msg.get('id'), 'elapsed': msg.get('elapsed'),
                'file': self._file_json(entry)}
        item.update(extra)
        self.timeline.append(item)
        return item

    def _add_change(self, entry, kind, index, msg, op, diffs, observed=(),
                    record=None):
        entry.changes_total += 1
        if len(entry.changes) >= self._events_cap:
            return None
        event = {
            'kind': kind, 'op': op, 'index': index, 'msg_id': msg.get('id'),
            'elapsed': msg.get('elapsed'), 'record': record,
            'ranges': [[pos, len(before)] for pos, before, _after in diffs],
            'observed_ranges': [[pos, length] for pos, length in observed],
            'before_hex': b''.join(b for _p, b, _a in diffs).hex(),
            'after_hex': b''.join(a for _p, _b, a in diffs).hex(),
        }
        entry.changes.append(event)
        return len(entry.changes) - 1

    # -- operations ------------------------------------------------------

    def _observe_select(self, d, df, df_path=None):
        fid = select_target_fid(d)
        if not fid or _is_df_fid(fid) or not _success(d):
            return
        # A path selection of an EF also enters the EF's parent DF
        # (TS 102 221 §8.4.1) — key the file by that DF, not the one the
        # channel was in before the SELECT, and keep the DF chain the
        # selection's own path spells out (DF_TELECOM/DF_PHONEBOOK/…).
        effective = selected_df_fid(d, df) or df
        _new_df, new_path = selected_df_state(d, df, df_path)
        self._entry(effective, fid,
                    df_path=new_path or df_path).counters['select'] += 1

    def _observe_get_response(self, d, state, channel, index, msg):
        response = d.get('response') or {}
        if d.get('response_for') == 'SELECT' and response:
            # The FCP of the selected file: learn the SFI relation and the
            # file facts (structure/size/records).
            fid = (state.get('sel') or {}).get('fid')
            if not fid or _is_df_fid(fid):
                return
            df = state.get('df') or '3f00'
            entry = self._entry(df, fid, df_path=state.get('df_path'))
            fd = response.get('file_descriptor')
            if isinstance(fd, dict):
                entry.structure = fd.get('structure', entry.structure)
                entry.record_len = fd.get('record_length', entry.record_len)
                entry.n_records = fd.get('num_records', entry.n_records)
            if response.get('file_size') is not None:
                entry.size = response['file_size']
            elif response.get('total_file_size') is not None:
                entry.size = response['total_file_size']
            if response.get('sfi') is not None:
                self._learn_sfi(df, response['sfi'], fid, entry)
            return
        if d.get('response_for') in _GR_READ_FOR:
            pending = self._pending_read.pop(channel, None)
            # Prefer the data-bearing GET RESPONSE's own attribution; an
            # SFI-addressed command keeps its context (the response's
            # attribution resolves against the current selection, not the SFI).
            src, src_df = d, state.get('df') or '3f00'
            src_path = state.get('df_path')
            if pending:
                _fid, sfi = self._file_ref(pending['d'], pending['df'])
                if sfi is not None:
                    src, src_df = pending['d'], pending['df']
                    src_path = pending.get('df_path')
            self._apply_read(src, src_df, index, msg, _body_bytes(d), src_path)

    def _observe_read(self, d, df, channel, index, msg, df_path=None):
        if not _success(d):
            return
        if not _body_bytes(d):
            # Data pending (T=0): the GET RESPONSE will carry it.
            self._pending_read[channel] = {'d': d, 'df': df,
                                           'df_path': df_path}
            return
        self._apply_read(d, df, index, msg, _body_bytes(d), df_path)

    def _apply_read(self, d, df, index, msg, data, df_path=None):
        if not data:
            return
        fid, sfi = self._file_ref(d, df)
        if fid is None:
            return
        entry = self._entry(df, fid, _file_label(d), df_path)
        if sfi is not None and entry.sfi is None:
            entry.sfi = sfi
        entry.counters['read'] += 1
        record = self._record_number(d)
        diffs, observed, _compared = entry.apply(record, self._offset(d, record), data)
        if entry.image_truncated:
            return
        if diffs:
            idx = self._add_change(entry, 'card', index, msg,
                                   d.get('ins_name') or '', diffs,
                                   observed=observed, record=record)
            self._push('card_change', entry, index, msg, record=record,
                       change_ref={'file': _key_str(entry.key), 'idx': idx}
                       if idx is not None else None)
        else:
            self._push('read', entry, index, msg, record=record)
        self._note_dir_content(d)

    def _observe_write(self, d, df, index, msg, df_path=None):
        data = _body_bytes(d)
        if not data or not _success(d):
            return
        fid, sfi = self._file_ref(d, df)
        if fid is None:
            return
        entry = self._entry(df, fid, _file_label(d), df_path)
        if sfi is not None and entry.sfi is None:
            entry.sfi = sfi
        entry.counters['update'] += 1
        record = self._record_number(d)
        diffs, observed, compared_all = entry.apply(record, self._offset(d, record), data)
        if entry.image_truncated:
            return
        change_ref = None
        if diffs or observed:
            idx = self._add_change(entry, 'device', index, msg,
                                   d.get('ins_name') or '', diffs,
                                   observed=observed, record=record)
            if idx is not None:
                change_ref = {'file': _key_str(entry.key), 'idx': idx}
        self._push('update', entry, index, msg, record=record, change_ref=change_ref,
                   no_change=(not diffs and compared_all))

    # -- helpers ---------------------------------------------------------

    def _offset(self, d, record):
        if record is not None:
            return 0
        return (d.get('p1p2') or {}).get('offset', 0)

    def _record_number(self, d):
        if d.get('ins_hex') not in ('b2', 'dc'):
            return None
        raw = (d.get('p1') or {}).get('raw')
        return int(raw, 16) if raw is not None else None

    def _note_dir_content(self, d):
        """Harvest AID -> label pairs from a surfaced EF.DIR."""
        apps = (d.get('file') or {}).get('applications')
        if not apps:
            return
        for app in apps:
            aid = (app.get('aid') or '').upper()
            if aid and app.get('label'):
                self.aid_labels[aid] = app['label']

    # -- result ----------------------------------------------------------

    def change_images(self, key, idx):
        """Before/after images of the unit affected by change *idx* of *key*.

        The unit is the whole file for transparent files, the changed record
        for record files.  The images are reconstructed from the current image
        by undoing the later events' changed bytes (every value change is an
        event, so the values are exact; a byte that was only *first observed*
        later can appear as known in both views).  The requested event's own
        ``observed_ranges`` are shown as unknown in the *before* view — that is
        what "newly observed" means.
        """
        entry = self.files.get(_parse_key(key))
        if entry is None or not 0 <= idx < len(entry.changes):
            return None
        event = entry.changes[idx]
        record = event.get('record')
        if record is None:
            buf = bytearray(entry.buf)
            mask = bytearray(entry.mask)
        else:
            buf = bytearray(entry.records.get(record, b''))
            mask = bytearray(entry.rec_mask.get(record, b''))
        for later in reversed(entry.changes[idx:]):   # the event itself included
            if later.get('record') != record:
                continue
            _apply_hex(buf, later['ranges'], later['before_hex'])
        # The before view: this event's newly observed bytes were unknown then.
        for pos, length in event.get('observed_ranges') or []:
            for i in range(pos, min(pos + length, len(mask))):
                mask[i] = 0
        before = _segments(buf, mask)
        # The after view: this event's changed bytes and its observations.
        _apply_hex(buf, event['ranges'], event['after_hex'])
        for pos, length in event.get('observed_ranges') or []:
            for i in range(pos, min(pos + length, len(mask))):
                mask[i] = 1
        after = _segments(buf, mask)
        return {
            'key': _key_str(entry.key),
            'name': entry.name,
            'path': _file_path(entry.df, entry.fid, entry.name,
                               self.aid_labels, entry.df_path),
            'df': entry.df,
            'fid': entry.fid,
            'structure': entry.structure,
            'size': entry.size,
            'record_len': entry.record_len,
            'n_records': entry.n_records,
            'record': record,
            'image_truncated': entry.image_truncated,
            'coverage': entry.coverage(),
            'kind': event['kind'],
            'op': event['op'],
            'index': event['index'],
            'msg_id': event.get('msg_id'),
            'elapsed': event.get('elapsed'),
            'ranges': event['ranges'],
            'observed_ranges': event.get('observed_ranges') or [],
            'before': before,
            'after': after,
        }

    def result(self, include_images=False):
        files = {}
        for key, entry in self.files.items():
            files[_key_str(key)] = {
                'name': entry.name,
                'path': _file_path(entry.df, entry.fid, entry.name,
                                   self.aid_labels, entry.df_path),
                'df': entry.df,
                'fid': entry.fid,
                'sfi': entry.sfi,
                'structure': entry.structure,
                'size': entry.size,
                'record_len': entry.record_len,
                'n_records': entry.n_records,
                'counters': dict(entry.counters),
                'coverage': entry.coverage(),
                'image_truncated': entry.image_truncated,
                'changes_total': entry.changes_total,
                'changes': entry.changes,
            }
        timeline = [{k: v for k, v in item.items() if k != 'entry'}
                    for item in self.timeline]
        return {
            'timeline': timeline,
            'timeline_total': len(timeline),
            'files': files,
            'sfi_relations': {df: {str(k): v for k, v in m.items()}
                              for df, m in self.sfi_relations.items()},
            'aid_labels': dict(self.aid_labels),
        }


def _merge_image(target, source):
    """Merge *source*'s observed image into *target* (used when a provisional
    SFI entry joins its resolved counterpart)."""
    if len(target.buf) < len(source.buf):
        target.buf.extend(b'\x00' * (len(source.buf) - len(target.buf)))
        target.mask.extend(b'\x00' * (len(source.buf) - len(target.mask)))
    for i, value in enumerate(source.buf):
        if source.mask[i] and not target.mask[i]:
            target.buf[i] = value
            target.mask[i] = 1
    for record, buf in source.records.items():
        mask = source.rec_mask[record]
        dst = target.records.setdefault(record, bytearray())
        dst_mask = target.rec_mask.setdefault(record, bytearray())
        if len(dst) < len(buf):
            dst.extend(b'\x00' * (len(buf) - len(dst)))
            dst_mask.extend(b'\x00' * (len(buf) - len(dst_mask)))
        for i, value in enumerate(buf):
            if mask[i] and not dst_mask[i]:
                dst[i] = value
                dst_mask[i] = 1
