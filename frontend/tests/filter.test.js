// The trace view's command filter: a set of entries — single command labels
// and conversation presets — with an empty set meaning "all commands".

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractConst, extractFunc } = require('./helpers.js');

const src = loadSrc();
let STATE = {};
const presetsSrc = src.match(/const FILTER_PRESETS = \[[\s\S]*?\n\];/);
assert.ok(presetsSrc, 'FILTER_PRESETS not found');
eval(
	presetsSrc[0].replace(/^const /m, 'var ') + '\n' +
	extractFunc(src, 'filterPreset') + '\n' +
	extractFunc(src, '_sw1') + '\n' +
	extractFunc(src, 'filter_label') + '\n' +
	extractFunc(src, '_ins_hex') + '\n' +
	extractFunc(src, 'matchesFilter') + '\n' +
	extractFunc(src, 'isOriginalCommand') + '\n' +
	extractFunc(src, 'filterEntryName') + '\n' +
	extractFunc(src, 'filterSummary') + '\n' +
	extractFunc(src, 'escapeHtml') + '\n' +
	'var _filterMenuSig = null;\n' +
	extractFunc(src, 'renderFilterMenu') + '\n' +
	'function t(x) { return x; }\n'
);
let el = () => ({});

function filterLabelOf(m) { return filter_label(m); }

const INS = {
	SELECT: 'a4', 'READ BINARY': 'b0', 'READ RECORD': 'b2',
	'UPDATE BINARY': 'd6', 'UPDATE RECORD': 'dc',
	FETCH: '12', 'TERMINAL PROFILE': '10', ENVELOPE: 'c2',
	'GET RESPONSE': 'c0',
};

function msg(name, opts = {}) {
	return {
		type: opts.type || 'tpdu',
		data: '',
		decoded: {
			ins_name: name,
			ins_hex: INS[name] || '00',
			sw: { sw1: opts.sw1 || '90', sw2: opts.sw2 || '00' },
			response_for: opts.response_for || null,
		},
	};
}

test('an empty filter shows every message', () => {
	STATE = { messages: [] };
	assert.equal(matchesFilter(msg('SELECT'), 0, new Set()), true);
	assert.equal(matchesFilter(msg('SELECT'), 0, null), true);
});

test('a single command label filters to that command', () => {
	const set = new Set(['cmd:SELECT']);
	assert.equal(matchesFilter(msg('SELECT'), 0, set), true);
	assert.equal(matchesFilter(msg('FETCH'), 0, set), false);
});

test('the GET RESPONSE linkage follows the selected commands', () => {
	const cmd = msg('SELECT');
	const gr = msg('GET RESPONSE', { response_for: 'SELECT' });
	STATE = { messages: [cmd, gr] };
	// Selecting the command brings its GET RESPONSE along …
	assert.equal(matchesFilter(gr, 1, new Set(['cmd:SELECT'])), true);
	// … and selecting GET RESPONSE keeps the commands it belongs to.
	assert.equal(matchesFilter(gr, 1, new Set(['cmd:GET RESPONSE'])), true);
	assert.equal(matchesFilter(cmd, 0, new Set(['cmd:GET RESPONSE'])), true);
	assert.equal(matchesFilter(msg('SELECT'), 0, new Set(['cmd:READ BINARY'])), false);
});

test('the proactive preset: FETCH, TERMINAL PROFILE and SW 91xx initiators', () => {
	const set = new Set(['preset:proactive']);
	assert.equal(matchesFilter(msg('FETCH'), 0, set), true);
	assert.equal(matchesFilter(msg('TERMINAL PROFILE'), 0, set), true);
	// A TERMINAL RESPONSE comes along through its 91xx answer, not its name.
	assert.equal(matchesFilter(msg('TERMINAL RESPONSE', { sw1: '91', sw2: '00' }), 0, set), true);
	assert.equal(matchesFilter(msg('ENVELOPE', { sw1: '91', sw2: '30' }), 0, set), true);
	assert.equal(matchesFilter(msg('UPDATE BINARY', { sw1: '91', sw2: '00' }), 0, set), true);
	// A plain ENVELOPE/TERMINAL RESPONSE (90 00) and unrelated commands stay out.
	assert.equal(matchesFilter(msg('ENVELOPE'), 0, set), false);
	assert.equal(matchesFilter(msg('TERMINAL RESPONSE'), 0, set), false);
	assert.equal(matchesFilter(msg('SELECT'), 0, set), false);
});

test('FETCH and TERMINAL RESPONSE are separate commands now', () => {
	// Every command keeps its own label; the multi-select filter (or the
	// preset's SW 91xx rule) covers the combinations.
	assert.equal(filterLabelOf(msg('FETCH')), 'FETCH');
	assert.equal(filterLabelOf(msg('TERMINAL RESPONSE')), 'TERMINAL RESPONSE');
	const set = new Set(['cmd:FETCH']);
	assert.equal(matchesFilter(msg('FETCH'), 0, set), true);
	assert.equal(matchesFilter(msg('TERMINAL RESPONSE'), 0, set), false);
	// The FETCH's GET RESPONSE (the proactive command itself) follows it.
	const gr = msg('GET RESPONSE', { response_for: 'FETCH' });
	STATE = { messages: [msg('FETCH'), gr] };
	assert.equal(matchesFilter(gr, 1, set), true);
});

test('the proactive+events preset adds ENVELOPE', () => {
	const set = new Set(['preset:proactive-events']);
	assert.equal(matchesFilter(msg('ENVELOPE'), 0, set), true);
	assert.equal(matchesFilter(msg('FETCH'), 0, set), true);
	assert.equal(matchesFilter(msg('SELECT'), 0, set), false);
});

test('the file-operations preset covers the five commands and their replies', () => {
	const set = new Set(['preset:files']);
	for (const name of ['SELECT', 'READ BINARY', 'READ RECORD', 'UPDATE BINARY',
	                    'UPDATE RECORD']) {
		assert.equal(matchesFilter(msg(name), 0, set), true, name);
	}
	assert.equal(matchesFilter(msg('FETCH'), 0, set), false);
	// The GET RESPONSE carrying a SELECT's FCP belongs to the conversation.
	assert.equal(matchesFilter(msg('GET RESPONSE', { response_for: 'SELECT' }), 0, set),
		true);
	assert.equal(matchesFilter(msg('GET RESPONSE', { response_for: 'FETCH' }), 0, set),
		false);
});

test('entries combine as a union', () => {
	const set = new Set(['preset:proactive', 'cmd:SELECT']);
	assert.equal(matchesFilter(msg('FETCH'), 0, set), true);
	assert.equal(matchesFilter(msg('SELECT'), 0, set), true);
	assert.equal(matchesFilter(msg('READ RECORD'), 0, set), false);
});

test('the summary follows the selection', () => {
	STATE = { filter: new Set() };
	assert.equal(filterSummary(), 'All commands');
	STATE.filter.add('cmd:SELECT');
	assert.equal(filterSummary(), 'SELECT');
	STATE.filter.clear();
	STATE.filter.add('preset:files');
	assert.equal(filterSummary(), 'File operations');
	STATE.filter.add('cmd:FETCH');
	assert.equal(filterSummary(), '2 commands');
});

test('the menu lists the presets and the commands with their counts', () => {
	STATE = {
		messages: [msg('SELECT'), msg('SELECT'), msg('FETCH')],
		filter: new Set(),
	};
	const menu = { innerHTML: '', style: { display: 'none' } };
	const btn = { textContent: '' };
	el = id => (id === 'filter-menu' ? menu : btn);
	renderFilterMenu(true);
	assert.match(menu.innerHTML, /data-filter="preset:proactive"/);
	assert.match(menu.innerHTML, /data-filter="preset:proactive-events"/);
	assert.match(menu.innerHTML, /data-filter="preset:files"/);
	assert.match(menu.innerHTML, /data-filter="cmd:SELECT"/);
	assert.match(menu.innerHTML, /<span class="filter-count">2<\/span>/);
	assert.match(menu.innerHTML, /data-filter="all" checked>/);
	assert.equal(btn.textContent, 'All commands');
	// A selection marks its row (and unchecks "All commands").
	STATE.filter.add('cmd:SELECT');
	renderFilterMenu(true);
	assert.match(menu.innerHTML, /data-filter="cmd:SELECT" checked>/);
	assert.match(menu.innerHTML, /data-filter="all">/);
	assert.equal(btn.textContent, 'SELECT');
});

test('the filter strings carry Russian translations', () => {
	const lang = extractConst(src, 'LANG_RU');
	const keys = new Set();
	for (const m of lang.matchAll(/'((?:[^'\\]|\\.)*)'\s*:/g)) {
		keys.add(m[1].replace(/\\(['\\])/g, '$1'));
	}
	for (const s of ['All commands', 'Presets', 'Commands', 'Proactive sessions',
		'Proactive + events', 'File operations', '{n} commands']) {
		assert.ok(keys.has(s), 'no LANG_RU entry for: ' + s);
	}
});

test('the filter dropdown is wired (source pins)', () => {
	assert.match(src, /<button type="button" id="filter-btn"[^>]*>/);
	assert.match(src, /<div class="filter-menu" id="filter-menu"/);
	assert.doesNotMatch(src, /id="filter-select"/);
	assert.match(src, /\$on\('filter-btn', 'click', \(\) => toggleFilterMenu\(\)\);/);
	assert.match(src, /\$on\('filter-menu', 'change', e => \{/);
	assert.match(src, /e\.target\.closest\('input\[data-filter\]'\)/);
	assert.match(src, /setFilterEntry\(box\.dataset\.filter, box\.checked\)/);
	assert.match(src, /if \(!e\.target\.closest\('#filter-dropdown'\)\) toggleFilterMenu\(false\);/);
	assert.match(src, /const filterSet = STATE\.filter;/);
	assert.match(src, /if \(!matchesFilter\(m, i, filterSet\)\) continue;/);
	assert.match(src, /clearFilter\(\);/);
	assert.match(src, /item\('all', t\('All commands'\), !STATE\.filter\.size\)/);
});
