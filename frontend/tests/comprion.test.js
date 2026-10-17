const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractConst, extractFunc } = require('./helpers.js');

const src = loadSrc();

// t() is a lookup stub: the tests assert on keys, not translations.
// The map getter keeps the const reachable outside the eval scope.
eval(
	'function t(x) { return x; }\n' +
	extractConst(src, 'IMPORT_ERROR_KEYS') + '\n' +
	extractFunc(src, 'comprionFileCheck') + '\n' +
	extractFunc(src, 'importErrorText') + '\n' +
	extractFunc(src, 'comprionSlotCheck') + '\n' +
	'function __errorKeys() { return IMPORT_ERROR_KEYS; }'
);

const PROTOCOL_HEAD = [
	'\t\t\t\t\t\t\t16.10.2026 15:10',
	'ISO Protocol Layer\t\t\t\t\t',
	'\t\tConfiguration\t\t\t',
	'\t\tUser:\t\tTest',
	'\t\tSession Name:\t\t2026-10-16 12h15m53s_AM_Android',
	'#\tSequence\tDir\tDescription\tValue\tDelay\tMeaning',
	'1\tCold reset\t\tEvent\t\t\tReset card interface',
].join('\r\n');

test('comprionFileCheck: protocol layer export passes', () => {
	assert.equal(comprionFileCheck(PROTOCOL_HEAD), '');
});

test('comprionFileCheck: application layer export is rejected', () => {
	const head = PROTOCOL_HEAD.replace('ISO Protocol Layer', 'ISO Application Layer');
	assert.equal(comprionFileCheck(head), 'app_layer');
});

test('comprionFileCheck: unrelated files are rejected', () => {
	assert.equal(comprionFileCheck(''), 'not_comprion');
	assert.equal(comprionFileCheck('hello world\n'), 'not_comprion');
	assert.equal(comprionFileCheck('#\tSequence\tDir\n1\tAPDU\n'), 'not_comprion');
});

test('comprionFileCheck: only the file head is inspected', () => {
	// The check reads the first lines only; a title buried deep in a large
	// file is not detected (the server performs the full validation).
	const deep = Array(20).fill('padding').join('\n') + '\nISO Protocol Layer\n';
	assert.equal(comprionFileCheck(deep), 'not_comprion');
});

test('importErrorText: server codes map to user-facing texts', () => {
	const keys = __errorKeys();
	for (const code of ['app_layer', 'not_comprion', 'unsupported_layout',
		'no_data', 'comprion_export']) {
		const text = importErrorText({ code, message: 'raw server text' });
		assert.equal(text, keys[code]);
		assert.ok(text.length > 10);
	}
});

test('importErrorText: unknown codes fall back to the server text', () => {
	assert.equal(importErrorText({ code: 'weird', message: 'boom' }), 'boom');
	assert.equal(importErrorText(new Error('boom')), 'boom');
	assert.equal(importErrorText(undefined), 'Import failed');
});

test('the PCAP import path is unchanged', () => {
	assert.match(src, /id="import-pcap-file"[^>]*accept="\.pcap,\.pcapng,\.cap"/);
	assert.match(src, /\$on\('import-pcap-btn', 'click', \(\) => el\('import-pcap-file'\)\.click\(\)\)/);
	// It still posts without a format (the server defaults to pcap).
	assert.match(src, /API\.importSession\(importBaseName\(file\), await file\.arrayBuffer\(\), ''\)/);
});

test('translatePage renders title attributes', () => {
	assert.match(src, /querySelectorAll\('\[data-l10n-title\]'\)/);
});

test('session names are escaped for attribute context', () => {
	// An imported Session Name reaches value="..." in the session list; a
	// quote must not break out of the attribute (local self-XSS).
	eval(extractFunc(src, 'escapeHtml'));
	assert.equal(escapeHtml('a"b'), 'a&quot;b');
	assert.equal(escapeHtml("a'b"), 'a&#39;b');
	assert.equal(escapeHtml('<x>&'), '&lt;x&gt;&amp;');
	assert.match(src, /value="\$\{escapeHtml\(name\)\}"/,
		'the session name must stay escaped in the list/grid templates');
});

test('COMPRION import strings carry Russian translations', () => {
	const lang = extractConst(src, 'LANG_RU');
	const keys = new Set();
	for (const m of lang.matchAll(/'((?:[^'\\]|\\.)*)'\s*:/g)) {
		keys.add(m[1].replace(/\\(['\\])/g, '$1'));
	}
	const strings = [
		...Object.values(__errorKeys()),
		'Import COMPRION trace',
		"Import the 'ISO Protocol Layer' export, optionally with the matching 'ISO Application Layer' export for exact timestamps.",
		'Select the ISO Protocol Layer export and, if available, the matching ISO Application Layer export of the same session.',
		'ISO Protocol Layer export (required)',
		'ISO Application Layer export (optional)',
		'Choose file…',
		'no file selected',
		'Import',
		'exact timestamps (Application Layer)',
		"Without the ISO Application Layer export the timeline is card/line activity time from the Protocol Layer's Delay column (the unit assumes 3.8 MHz) — the order is right, but host pauses are missing and the absolute times are not exact.",
		'The ISO Application Layer export adds exact per-APDU timestamps (ms precision) — the session window and the gaps between APDUs become exact. Both files are verified to belong to the same session before importing.',
	];
	for (const s of strings) {
		assert.ok(keys.has(s), 'no LANG_RU entry for: ' + s);
	}
});

test('the COMPRION import is a two-slot dialog', () => {
	// Two separate pickers (a required Protocol Layer slot and an optional
	// Application Layer time-base slot), an Import button gated on the
	// protocol file, and an in-dialog error area.
	assert.match(src, /id="comprion-modal"/);
	assert.match(src, /id="comprion-protocol-file"[^>]*accept="\.txt,\.tsv"/);
	assert.match(src, /id="comprion-application-file"[^>]*accept="\.txt,\.tsv"/);
	assert.match(src, /id="comprion-import"[^>]*disabled/);
	assert.doesNotMatch(src, /import-comprion-file"/);
	assert.doesNotMatch(src, /classifyComprionFiles/);
	assert.match(src, /importComprionBundle/);
	assert.match(src, /time_base === 'application-layer'/);
	assert.match(src, /\$on\('import-comprion-btn', 'click', openComprionDialog\)/);
	assert.match(src, /\$on\('comprion-cancel', 'click', closeComprionDialog\)/);
	assert.match(src, /e\.key !== 'Escape'/);
});

test('comprionSlotCheck: slot/kind outcomes', () => {
	assert.equal(comprionSlotCheck('protocol', ''), '');
	assert.equal(comprionSlotCheck('protocol', 'app_layer'), 'app_layer');
	assert.equal(comprionSlotCheck('protocol', 'not_comprion'), 'not_comprion');
	assert.equal(comprionSlotCheck('application', 'app_layer'), '');
	assert.equal(comprionSlotCheck('application', ''), 'protocol_slot');
	assert.equal(comprionSlotCheck('application', 'not_comprion'), 'not_comprion');
	// Every outcome has a message.
	const keys = __errorKeys();
	for (const code of ['app_layer', 'protocol_slot', 'not_comprion', 'identical']) {
		assert.ok(keys[code], 'no message for: ' + code);
	}
});

// ── dialog state machine (with a minimal DOM/API stub) ─────────────────
const DLG_NODES = new Map();
function dlgEl(id) {
	if (!DLG_NODES.has(id)) {
		const classes = new Set();
		DLG_NODES.set(id, {
			id, textContent: '', disabled: false, value: '', files: [],
			classList: {
				add: c => classes.add(c),
				remove: c => classes.delete(c),
				contains: c => classes.has(c),
			},
		});
	}
	return DLG_NODES.get(id);
}

eval(
	'var IMPORT_ERROR_KEYS = __errorKeys();\n' +
	'function el(id) { return dlgEl(id); }\n' +
	extractConst(src, 'COMPRION_DLG').replace('const ', 'var ') + '\n' +
	extractFunc(src, 'comprionSameFile') + '\n' +
	extractFunc(src, 'renderComprionDialog') + '\n' +
	extractFunc(src, 'openComprionDialog') + '\n' +
	extractFunc(src, 'closeComprionDialog') + '\n' +
	extractFunc(src, 'comprionPick') + '\n' +
	extractFunc(src, 'importBaseName') + '\n' +
	extractFunc(src, 'importSuccessText') + '\n' +
	extractFunc(src, 'confirmComprionImport') + '\n' +
	'var IMPORT_CALLS = []; var IMPORT_FAIL = null; var IMPORT_MSG = [];\n' +
	'var API = {\n' +
	'  importComprionBundle: async (name, text, times) => {\n' +
	'    IMPORT_CALLS.push(["bundle", name, text.length, times.length]);\n' +
	'    if (IMPORT_FAIL) throw IMPORT_FAIL;\n' +
	'    return {name: "S", message_count: 7, time_base: "application-layer"};\n' +
	'  },\n' +
	'  importSession: async (name, bytes, fmt) => {\n' +
	'    IMPORT_CALLS.push(["raw", name, fmt]);\n' +
	'    if (IMPORT_FAIL) throw IMPORT_FAIL;\n' +
	'    return {name: "S", message_count: 3, time_base: "delays"};\n' +
	'  },\n' +
	'};\n' +
	'function importMsg(text, error) { IMPORT_MSG.push([text, !!error]); }\n' +
	'function loadSessions() {}\n'
);

function enactFile(name, head) {
	return {
		name, size: head.length + 1,
		slice: () => ({ text: async () => head }),
		text: async () => head,
		arrayBuffer: async () => new ArrayBuffer(0),
	};
}

const APP_HEAD = PROTOCOL_HEAD.replace('ISO Protocol Layer', 'ISO Application Layer');

test('COMPRION dialog: slot validation and import gating', async () => {
	openComprionDialog();
	assert.ok(el('comprion-modal').classList.contains('show'));
	assert.equal(el('comprion-import').disabled, true, 'no file -> no import');
	assert.equal(el('comprion-protocol-name').textContent, 'no file selected');

	// Wrong layer in the protocol slot: error, slot stays empty.
	await comprionPick('protocol', enactFile('app.txt', APP_HEAD));
	assert.equal(COMPRION_DLG.protocol, null);
	assert.equal(COMPRION_DLG.error, 'app_layer');
	assert.equal(el('comprion-import').disabled, true);

	// The Protocol Layer export in the protocol slot.
	const proto = enactFile('proto.txt', PROTOCOL_HEAD);
	await comprionPick('protocol', proto);
	assert.equal(COMPRION_DLG.error, '');
	assert.equal(el('comprion-protocol-name').textContent, 'proto.txt');
	assert.equal(el('comprion-import').disabled, false);

	// The Protocol Layer export in the application slot.
	await comprionPick('application', enactFile('p2.txt', PROTOCOL_HEAD));
	assert.equal(COMPRION_DLG.application, null);
	assert.equal(COMPRION_DLG.error, 'protocol_slot');

	// An unrelated file in the application slot.
	await comprionPick('application', enactFile('x.txt', 'hello'));
	assert.equal(COMPRION_DLG.error, 'not_comprion');

	// The same file in both slots.
	await comprionPick('application', enactFile('proto.txt', PROTOCOL_HEAD));
	assert.equal(COMPRION_DLG.application, null);
	assert.equal(COMPRION_DLG.error, 'identical');
	assert.notEqual(COMPRION_DLG.protocol, null);

	// A valid application file clears the error.
	await comprionPick('application', enactFile('app.txt', APP_HEAD));
	assert.equal(COMPRION_DLG.error, '');
	assert.ok(el('comprion-hint').textContent.includes('exact per-APDU timestamps'));

	closeComprionDialog();
	assert.equal(el('comprion-modal').classList.contains('show'), false);
});

test('COMPRION dialog: success closes, server errors stay', async () => {
	// Success with both files: one JSON bundle, dialog closed.
	openComprionDialog();
	await comprionPick('protocol', enactFile('proto.txt', PROTOCOL_HEAD));
	await comprionPick('application', enactFile('app.txt', APP_HEAD));
	IMPORT_CALLS.length = 0;
	await confirmComprionImport();
	assert.deepEqual(IMPORT_CALLS,
		[['bundle', 'proto', PROTOCOL_HEAD.length, APP_HEAD.length]]);
	assert.equal(el('comprion-modal').classList.contains('show'), false);
	assert.ok(IMPORT_MSG.some(([text]) => text.includes('exact timestamps')));

	// Protocol Layer only: the raw-body path.
	openComprionDialog();
	await comprionPick('protocol', enactFile('proto.txt', PROTOCOL_HEAD));
	IMPORT_CALLS.length = 0;
	await confirmComprionImport();
	assert.deepEqual(IMPORT_CALLS, [['raw', 'proto', 'comprion']]);
	assert.equal(el('comprion-modal').classList.contains('show'), false);

	// A server error keeps the dialog open with both selections intact.
	openComprionDialog();
	await comprionPick('protocol', enactFile('proto.txt', PROTOCOL_HEAD));
	await comprionPick('application', enactFile('app.txt', APP_HEAD));
	IMPORT_FAIL = Object.assign(new Error('mismatch'), { code: 'session_mismatch' });
	await confirmComprionImport();
	IMPORT_FAIL = null;
	assert.equal(el('comprion-modal').classList.contains('show'), true);
	assert.equal(COMPRION_DLG.error, 'session_mismatch');
	assert.ok(COMPRION_DLG.protocol && COMPRION_DLG.application);
	assert.equal(el('comprion-import').disabled, false, 'import can be retried');

	closeComprionDialog();
});

// ── Files view (per-file operation timeline) ───────────────────────────
eval(
	'function t(x) { return x; }\n' +
	extractFunc(src, 'fileOpClass') + '\n' +
	extractFunc(src, 'fileOpVerb') + '\n' +
	extractFunc(src, 'fileOpLabel') + '\n' +
	extractFunc(src, 'escapeHtml') + '\n' +
	extractFunc(src, 'hexImageRows')
);

test('Files view: operation kinds map to classes and verbs', () => {
	assert.equal(fileOpClass('read'), 'file-op-read');
	assert.equal(fileOpClass('update'), 'file-op-update');
	assert.equal(fileOpClass('card_change'), 'file-op-card');
	assert.equal(fileOpVerb('read'), 'Read');
	assert.equal(fileOpVerb('update'), 'Update');
	assert.equal(fileOpVerb('card_change'), 'Changed on card');
	assert.equal(fileOpLabel({kind: 'read', file: {name: 'EF_ICCID'}}), 'Read EF_ICCID');
	assert.equal(fileOpLabel({kind: 'card_change', file: {name: 'EF_LOCI'}}),
		'Changed on card EF_LOCI');
	assert.equal(fileOpLabel({kind: 'read', file: null}), 'Read ?');
});

test('Files view: the hex image rows mark changed, new and unknown bytes', () => {
	// 'ABCD' then a gap, then 'ef' newly observed.
	const view = hexImageRows(
		[{offset: 0, hex: '41424344'}, {offset: 8, hex: '6566'}],
		[[2, 1]],       // changed
		[[8, 2]]);      // newly observed
	assert.equal(view.truncated, false);
	assert.equal(view.end, 10);
	assert.equal(view.rows.length, 1);
	const cells = view.rows[0].cells;
	assert.deepEqual(cells[0], {hex: '41', cls: ''});
	assert.deepEqual(cells[2], {hex: '43', cls: 'hex-changed'});
	assert.deepEqual(cells[4], {hex: '--', cls: 'hex-unknown'});   // the gap
	assert.deepEqual(cells[8], {hex: '65', cls: 'hex-new'});
	// No ASCII column any more (it wasted the modal's width).
	assert.equal(view.rows[0].ascii, undefined);
});

test('Files view: the hex image respects the row limit', () => {
	const view = hexImageRows([{offset: 0, hex: 'aa'.repeat(64)}], [], [], 32);
	assert.equal(view.truncated, true);
	assert.equal(view.rows.length, 2);
	assert.equal(view.end, 64);
});

test('Files view: the view selector (topbar) and the timeline are wired', () => {
	assert.match(src, /<select class="side-view-select" id="side-view-select"[^>]*>/);
	// The selector is a topbar control (before the two-column trace area), so
	// it stays visible while the side panel scrolls.
	const topbar = src.indexOf('<div class="trace-topbar">');
	const sel = src.indexOf('id="side-view-select"');
	const main = src.indexOf('<div class="trace-main">');
	assert.ok(topbar >= 0 && topbar < sel && sel < main, 'selector in the topbar');
	assert.match(src, /<option value="files" data-l10n="Files">/);
	assert.doesNotMatch(src, /class="side-tab/);
	assert.match(src, /id="file-view"/);
	assert.match(src, /id="file-diff-modal"/);
	assert.match(src, /id="file-diff-body"/);
	assert.match(src, /\$on\('side-view-select', 'change'/);
	assert.match(src, /\$on\('file-view', 'click'/);
	assert.match(src, /API\.getSessionFiles\(sid\)/);
	assert.match(src, />\$\{t\('Details'\)\}<\/button>/);
	assert.match(src, /API\.getSessionFileImage\(STATE\.sessionViewId, fileKey, idx\)/);
	assert.match(src, /getSessionFileImage\(id, key, change\)/);
	assert.match(src, /files\/image\?key=/);
	assert.match(src, /if \(row\) jumpToMessage\(Number\(row\.dataset\.idx\)\);/);
	assert.match(src, /getSessionFiles\(id\)\s*\{ return this\._fetch\('GET', `\/api\/sessions\/\$\{id\}\/files`\); \}/);
});

test('Files view: strings carry Russian translations', () => {
	const lang = extractConst(src, 'LANG_RU');
	const keys = new Set();
	for (const m of lang.matchAll(/'((?:[^'\\]|\\.)*)'\s*:/g)) {
		keys.add(m[1].replace(/\\(['\\])/g, '$1'));
	}
	for (const s of ['Files', 'Read', 'Update', 'Changed on card', 'Change details',
		'Details', 'Close', 'Offset', 'Record', 'Before', 'After', 'Show the change',
		'changed', 'newly observed', 'never observed',
		'{c} bytes changed, {n} bytes newly observed',
		'Showing the first {n} bytes of the image',
		'The image is frozen (size cap reached) — later changes are not tracked.',
		'No file operations recorded', 'Failed to load files', 'Loading…']) {
		assert.ok(keys.has(s), 'no LANG_RU entry for: ' + s);
	}
});

// ── Files view against the real API layer (fetch stubbed) ──────────────
// Reuses the t()/el() stubs from the dialog block above.
eval(
	'var localStorage = { getItem: () => "", setItem: () => {} };\n' +
	extractConst(src, 'STATE').replace('const ', 'var ') + '\n' +
	'function API_BASE() { return "http://test"; }\n' +
	'function updateCaptureButton() {}\n' +
	'var __fetchImpl = null;\n' +
	'var fetch = (...a) => __fetchImpl(...a);\n' +
	extractConst(src, 'API') + '\n' +
	extractFunc(src, 'escapeHtml') + '\n' +
	extractFunc(src, 'fileOpClass') + '\n' +
	extractFunc(src, 'fileOpVerb') + '\n' +
	extractFunc(src, 'fileOpLabel') + '\n' +
	extractFunc(src, 'renderFileView') + '\n' +
	'function __filesApi() { return API; }'
);

function fetchReply(status, body) {
	return async () => ({
		ok: status >= 200 && status < 300, status,
		json: async () => body,
	});
}

test('API._fetch: an HTTP error throws and does not look like data', async () => {
	const api = __filesApi();
	__fetchImpl = fetchReply(200, {a: 1});
	assert.deepEqual(await api._fetch('GET', '/x'), {a: 1});
	STATE.serverAvailable = true;
	__fetchImpl = fetchReply(404, {error: 'Session not found'});
	await assert.rejects(() => api._fetch('GET', '/y'), /Session not found/);
	assert.equal(STATE.serverAvailable, true, 'HTTP errors are not disconnects');
	__fetchImpl = async () => { throw new Error('network'); };
	await assert.rejects(() => api._fetch('GET', '/z'), /network/);
	assert.equal(STATE.serverAvailable, false, 'network errors do');
});

test('Files view: a valid payload renders the timeline', async () => {
	__fetchImpl = fetchReply(200, {
		timeline: [{kind: 'read', index: 3, file: {name: 'EF_ICCID'}}],
		files: {}, timeline_total: 1,
	});
	STATE.sessionViewId = 7; STATE.filesData = null; STATE.filesSessionId = null;
	await renderFileView();
	assert.match(el('file-view').innerHTML, /Read EF_ICCID/);
	assert.equal(STATE.filesSessionId, 7);
});

test('Files view: an empty payload is the empty state, not an error', async () => {
	__fetchImpl = fetchReply(200, {timeline: [], files: {}, timeline_total: 0});
	STATE.sessionViewId = 8; STATE.filesData = null; STATE.filesSessionId = null;
	await renderFileView();
	assert.match(el('file-view').innerHTML, /No file operations recorded/);
	assert.doesNotMatch(el('file-view').innerHTML, /Failed to load files/);
});

test('Files view: an error is shown with its reason and never cached', async () => {
	let calls = 0;
	__fetchImpl = async () => {
		calls++;
		return {ok: false, status: 404, json: async () => ({error: 'Session not found'})};
	};
	STATE.sessionViewId = 9; STATE.filesData = null; STATE.filesSessionId = null;
	await renderFileView();
	assert.match(el('file-view').innerHTML, /Failed to load files/);
	assert.match(el('file-view').innerHTML, /Session not found/);
	assert.equal(STATE.filesData, null, 'a failure must not be cached');
	assert.equal(STATE.filesSessionId, null);
	// The next visit retries (and this time succeeds).
	__fetchImpl = fetchReply(200, {
		timeline: [{kind: 'update', index: 1, file: {name: 'EF_LOCI'}}],
		files: {}, timeline_total: 1,
	});
	await renderFileView();
	assert.match(el('file-view').innerHTML, /Update EF_LOCI/);
	assert.equal(calls, 1);
});

test('Files view: a response for a session left meanwhile is ignored', async () => {
	let resolveIt;
	const pending = new Promise(r => { resolveIt = r; });
	__fetchImpl = async () => ({ok: true, status: 200, json: () => pending});
	STATE.sessionViewId = 10; STATE.filesData = null; STATE.filesSessionId = null;
	const render = renderFileView();
	STATE.sessionViewId = 11;   // the user opened another session meanwhile
	resolveIt({timeline: [{kind: 'read', index: 0, file: {name: 'STALE'}}],
		files: {}, timeline_total: 1});
	await render;
	assert.doesNotMatch(el('file-view').innerHTML, /STALE/);
	assert.equal(STATE.filesData, null);
	assert.equal(STATE.filesSessionId, null);
});

// ── Change-details modal rendering (stubbed DOM) ───────────────────────
eval(
	'function el(id) { return dlgEl(id); }\n' +
	extractFunc(src, 'fmt_elapsed') + '\n' +
	extractFunc(src, 'escapeHtml') + '\n' +
	extractFunc(src, 'hexImageRows') + '\n' +
	extractFunc(src, 'hexImageHtml') + '\n' +
	extractFunc(src, 'renderFileDiff')
);

test('Change details modal: header, summary, legend and both views', () => {
	renderFileDiff({
		name: 'EF_ICCID',
		path: 'MF/EF_ICCID (2FE2)',
		op: 'READ BINARY',
		record: null,
		n_records: null,
		index: 12,
		elapsed: 3.25,
		ranges: [[8, 2]],
		observed_ranges: [[0, 4]],
		before: [{offset: 0, hex: '41424344'}],
		after: [{offset: 0, hex: '41424344'}, {offset: 8, hex: '9900'}],
		image_truncated: false,
	});
	const sub = el('file-diff-sub').textContent;
	assert.match(sub, /MF\/EF_ICCID \(2FE2\) — READ BINARY/);
	assert.match(sub, /#12/);
	const body = el('file-diff-body').innerHTML;
	assert.match(body, /2 bytes changed, 4 bytes newly observed/);
	assert.match(body, /hex-cell hex-changed/);     // legend + the changed byte
	assert.match(body, /hex-cell hex-new/);
	assert.match(body, /hex-cell hex-unknown/);
	assert.match(body, /Before/);
	assert.match(body, /After/);
	assert.equal((body.match(/class="hex-view"/g) || []).length, 2);
	// The legend sits below the two views, each swatch bound to its label.
	assert.ok(body.indexOf('hex-legend') > body.lastIndexOf('hex-view'));
	assert.equal((body.match(/class="hex-legend-item"/g) || []).length, 3);
	// The record header variant and the frozen-image note.
	renderFileDiff({
		name: 'EF_IMSI', op: 'READ RECORD', record: 2, n_records: 5, index: 40,
		elapsed: 9.5, ranges: [[0, 1]], observed_ranges: [],
		before: [{offset: 0, hex: 'aa'}], after: [{offset: 0, hex: 'bb'}],
		image_truncated: true,
	});
	assert.match(el('file-diff-sub').textContent, /Record 2 \/ 5/);
	assert.match(el('file-diff-body').innerHTML, /image is frozen/);
});

// ── Session loading must survive "no active capture" ───────────────────
eval(extractFunc(src, 'stopCaptureIfRunning'));

test('stopCaptureIfRunning tolerates "no active capture" (400)', async () => {
	let calls = 0;
	API.stopCapture = async () => {
		calls++;
		throw Object.assign(new Error('No active capture'), {status: 400});
	};
	await stopCaptureIfRunning();          // must resolve, not reject
	assert.equal(calls, 1);
	API.stopCapture = async () => { calls++; };
	await stopCaptureIfRunning();
	assert.equal(calls, 2);
});

test('importSuccessText mentions skipped non-APDU packets', () => {
	const text = importSuccessText({name: 'x', message_count: 3, skipped: 2});
	assert.match(text, /3 messages/);
	assert.match(text, /2 packets skipped \(not APDU-shaped\)/);
	assert.doesNotMatch(importSuccessText({name: 'x', message_count: 3}), /skipped/);
});

test('loadSession stops a capture tolerantly', () => {
	const body = extractFunc(src, 'loadSession');
	assert.match(body, /await stopCaptureIfRunning\(\)/);
	assert.doesNotMatch(body, /await API\.stopCapture\(\)/);
	// The capture button also resets its state after a tolerated stop.
	const stop = extractFunc(src, 'stopCapture');
	assert.match(stop, /await stopCaptureIfRunning\(\)/);
	assert.match(stop, /STATE\.captureActive = false;/);
});
