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
	extractFunc(src, 'fileDiffRows')
);

test('Files view: operation kinds map to classes and verbs', () => {
	assert.equal(fileOpClass('read'), 'file-op-read');
	assert.equal(fileOpClass('update'), 'file-op-update');
	assert.equal(fileOpClass('card_change'), 'file-op-card');
	assert.equal(fileOpVerb('read'), 'Read');
	assert.equal(fileOpVerb('update'), 'Update');
	assert.equal(fileOpVerb('card_change'), 'Changed (card)');
	assert.equal(fileOpLabel({kind: 'read', file: {name: 'EF_ICCID'}}), 'Read EF_ICCID');
	assert.equal(fileOpLabel({kind: 'card_change', file: {name: 'EF_LOCI'}}),
		'Changed (card) EF_LOCI');
	assert.equal(fileOpLabel({kind: 'read', file: null}), 'Read ?');
});

test('Files view: the diff rows slice the concatenated hex', () => {
	const change = {
		ranges: [[8, 2], [16, 1]],
		before_hex: '95f9aa',
		after_hex: '000001',
	};
	assert.deepEqual(fileDiffRows(change), [
		{pos: 8, len: 2, before: '95f9', after: '0000'},
		{pos: 16, len: 1, before: 'aa', after: '01'},
	]);
	assert.deepEqual(fileDiffRows({ranges: [], before_hex: '', after_hex: ''}), []);
});

test('Files view: side-panel dropdown and the timeline are wired', () => {
	assert.match(src, /<select class="side-view-select" id="side-view-select"[^>]*>/);
	assert.match(src, /<option value="files" data-l10n="Files">/);
	assert.doesNotMatch(src, /class="side-tab/);
	assert.match(src, /id="file-view"/);
	assert.match(src, /id="file-diff-modal"/);
	assert.match(src, /id="file-diff-body"/);
	assert.match(src, /\$on\('side-view-select', 'change'/);
	assert.match(src, /\$on\('file-view', 'click'/);
	assert.match(src, /API\.getSessionFiles\(STATE\.sessionViewId\)/);
	assert.match(src, /if \(row\) jumpToMessage\(Number\(row\.dataset\.idx\)\);/);
	assert.match(src, /getSessionFiles\(id\)\s*\{ return this\._fetch\('GET', `\/api\/sessions\/\$\{id\}\/files`\); \}/);
});

test('Files view: strings carry Russian translations', () => {
	const lang = extractConst(src, 'LANG_RU');
	const keys = new Set();
	for (const m of lang.matchAll(/'((?:[^'\\]|\\.)*)'\s*:/g)) {
		keys.add(m[1].replace(/\\(['\\])/g, '$1'));
	}
	for (const s of ['Files', 'Read', 'Update', 'Changed (card)', 'Card-side change',
		'Close', 'Offset', 'Record', 'Before', 'After', 'Show the change',
		'No file operations recorded', 'Failed to load files', 'Loading…']) {
		assert.ok(keys.has(s), 'no LANG_RU entry for: ' + s);
	}
});
