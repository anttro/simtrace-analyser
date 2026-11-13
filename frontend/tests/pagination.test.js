// A saved session's message list is fetched in pages (the API caps a page at
// 500).  The Trace view used to show only the first page with no way to see
// the rest, and the status bar claimed "500 messages" for a 923-message
// session.  The counter now reports loaded/total and a footer button appends
// the next page without throwing the reader back to the top; the Files-view
// jump and the button share one request per page so no row is duplicated.

const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractFunc } = require('./helpers.js');

const src = loadSrc();

let STATE = {};
let API = {};
let renders = [];
let alerts = [];
let focused = [];
let list = { scrollTop: 0, scrollHeight: 0 };
let el = () => ({});
let _filesJumpTimer = null;
function renderMessages(skipScroll) {
	renders.push(skipScroll);
	// A real render rewrites the list's content, which resets its scroll.
	list.scrollTop = 0;
}
function focusMessage(idx) { focused.push(idx); }
function fileViewSessionId() { return STATE.sessionViewId; }
function alert(msg) { alerts.push(msg); }
function t(x) { return x; }

// A `const` in a direct eval stays scoped to the eval; the map is extracted
// as a var so the extracted functions can see it (like FILTER_PRESETS).
const pageMapSrc = src.match(/const _sessionPageRequests = new Map\(\);/);
assert.ok(pageMapSrc, '_sessionPageRequests not found');
eval(
	pageMapSrc[0].replace(/^const /, 'var ') + '\n' +
	extractFunc(src, 'fetchSessionPage') + '\n' +
	extractFunc(src, 'messagesCountText') + '\n' +
	extractFunc(src, 'loadMoreMessages') + '\n' +
	extractFunc(src, 'jumpToMessage') + '\n'
);

// Each test starts from a settled page map (a leftover pending request would
// be shared with the next test's stub).
function resetPaging() {
	_sessionPageRequests.clear();
	renders = [];
	alerts = [];
	focused = [];
}

// ── the status bar counter ─────────────────────────────────────────────

test('the saved-session counter shows loaded / total until the last page', () => {
	assert.equal(messagesCountText(500, 923), '500 / 923 messages');
	assert.equal(messagesCountText(923, 923), '923 messages');
	// A stale total below the loaded count must not fabricate a smaller one.
	assert.equal(messagesCountText(1000, 923), '1000 messages');
});

test('a live capture keeps the plain message count', () => {
	// The live path passes loaded === total, so nothing changes there.
	assert.equal(messagesCountText(1810, 1810), '1810 messages');
	assert.equal(messagesCountText(0, 0), '0 messages');
});

test('the counter is translated', () => {
	assert.match(src, /'\{a\} \/ \{b\} messages': '\{a\} \/ \{b\} сообщений'/);
});

test('updateStatus uses the session total for a saved session', () => {
	const body = extractFunc(src, 'updateStatus');
	assert.match(body, /const total = STATE\.sessionViewId !== null \? STATE\.sessionTotal : STATE\.messages\.length;/);
	assert.match(body, /count\.textContent = messagesCountText\(STATE\.messages\.length, total\);/);
	// No stale plain count remains in the status bar.
	assert.doesNotMatch(body, /t\('\{n\} messages'\)/);
});

// ── loadMoreMessages ───────────────────────────────────────────────────

test('the next page is appended at the loaded offset and keeps the scroll', async () => {
	resetPaging();
	list = { scrollTop: 120, scrollHeight: 4000 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	const calls = [];
	API = {
		getSession: async (sid, from) => {
			calls.push([sid, from]);
			return { messages: new Array(423).fill(0), total: 923 };
		},
	};
	await loadMoreMessages();
	assert.deepEqual(calls, [[240, 500]]);
	assert.equal(STATE.messages.length, 923);
	assert.equal(STATE.sessionTotal, 923);
	assert.equal(STATE.loadingMore, false);
	// A render before (button → "Loading…") and after (button gone) the fetch.
	assert.deepEqual(renders, [true, true]);
	assert.deepEqual(alerts, []);
	// The reader stays where they clicked, not at the top of the longer list.
	assert.equal(list.scrollTop, 120);
});

test('a page that reveals more messages keeps the footer possible', async () => {
	resetPaging();
	list = { scrollTop: 40, scrollHeight: 1000 };
	el = () => list;
	STATE = { sessionViewId: 238, sessionTotal: 1810, loadingMore: false,
		messages: new Array(500).fill(0) };
	API = { getSession: async () => ({ messages: new Array(500).fill(0), total: 1810 }) };
	await loadMoreMessages();
	assert.equal(STATE.messages.length, 1000);
	assert.equal(STATE.sessionTotal, 1810);
	assert.equal(list.scrollTop, 40);
});

test('a live capture has no paging', async () => {
	resetPaging();
	STATE = { sessionViewId: null, sessionTotal: 0, loadingMore: false, messages: [] };
	API = { getSession: async () => { throw new Error('must not fetch'); } };
	await loadMoreMessages();
	assert.deepEqual(renders, []);
});

test('a page already loading is not requested twice', async () => {
	resetPaging();
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: true,
		messages: new Array(500).fill(0) };
	API = { getSession: async () => { throw new Error('must not fetch'); } };
	await loadMoreMessages();
	assert.deepEqual(renders, []);
});

test('a fully loaded session requests nothing', async () => {
	resetPaging();
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(923).fill(0) };
	API = { getSession: async () => { throw new Error('must not fetch'); } };
	await loadMoreMessages();
	assert.deepEqual(renders, []);
});

test('a failure keeps the loaded messages and reports it once', async () => {
	resetPaging();
	list = { scrollTop: 77, scrollHeight: 3000 };
	el = () => list;
	STATE = { sessionViewId: 216, sessionTotal: 1991, loadingMore: false,
		messages: new Array(500).fill(0) };
	API = { getSession: async () => { throw new Error('offline'); } };
	await loadMoreMessages();
	assert.equal(STATE.messages.length, 500);
	assert.equal(STATE.sessionTotal, 1991);
	assert.equal(STATE.loadingMore, false);
	assert.deepEqual(alerts, ['Failed to load session']);
	assert.deepEqual(renders, [true, true]);
	assert.equal(list.scrollTop, 77);
});

test('a page arriving after a session switch is dropped', async () => {
	resetPaging();
	list = { scrollTop: 10, scrollHeight: 500 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	API = {
		getSession: async () => {
			// The reader opened another session while the page was in flight.
			STATE.sessionViewId = 238;
			STATE.messages = [];
			STATE.sessionTotal = 1810;
			STATE.loadingMore = false;
			return { messages: new Array(423).fill(0), total: 923 };
		},
	};
	await loadMoreMessages();
	assert.equal(STATE.sessionViewId, 238);
	assert.equal(STATE.messages.length, 0);
	assert.equal(STATE.sessionTotal, 1810);
	assert.equal(list.scrollTop, 10);
	assert.deepEqual(alerts, []);
});

test('a page appended by a concurrent caller is not added twice', async () => {
	resetPaging();
	list = { scrollTop: 5, scrollHeight: 500 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	API = {
		getSession: async () => {
			// The Files-view jump got the same page first and appended it.
			STATE.messages.push(...new Array(423).fill(0));
			return { messages: new Array(423).fill(0), total: 923 };
		},
	};
	await loadMoreMessages();
	assert.equal(STATE.messages.length, 923);
	assert.equal(STATE.sessionTotal, 923);
	assert.deepEqual(alerts, []);
});

test('an empty page collapses the total instead of offering it again', async () => {
	resetPaging();
	list = { scrollTop: 0, scrollHeight: 100 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	let calls = 0;
	API = {
		getSession: async () => {
			calls++;
			return { messages: [], total: 923 };
		},
	};
	await loadMoreMessages();
	assert.equal(calls, 1);
	assert.equal(STATE.messages.length, 500);
	// The card says there is more, the page says otherwise: trust the page.
	assert.equal(STATE.sessionTotal, 500);
	// The footer is gone, so a second click is a no-op (no request loop).
	renders = [];
	await loadMoreMessages();
	assert.equal(calls, 1);
	assert.deepEqual(renders, []);
});

// ── the shared page request ────────────────────────────────────────────

test('the same (session, offset) page is requested once', async () => {
	resetPaging();
	const calls = [];
	const pending = [];
	API = {
		getSession: (sid, from) => {
			calls.push([sid, from]);
			return new Promise(resolve => pending.push(resolve));
		},
	};
	const a = fetchSessionPage(240, 500);
	const b = fetchSessionPage(240, 500);
	assert.equal(a, b);
	assert.deepEqual(calls, [[240, 500]]);
	// A different offset is a different page.
	const c = fetchSessionPage(240, 1000);
	assert.notEqual(a, c);
	assert.deepEqual(calls, [[240, 500], [240, 1000]]);
	pending.forEach(resolve => resolve({ messages: [], total: 5 }));
	await a;
	await c;
	// Once settled the entry is dropped: a later click fetches again.
	await Promise.resolve();
	const d = fetchSessionPage(240, 500);
	assert.deepEqual(calls, [[240, 500], [240, 1000], [240, 500]]);
	pending[2]({ messages: [], total: 5 });
	await d;
});

test('a jump and a Load more share one page (no duplicate rows)', async () => {
	resetPaging();
	list = { scrollTop: 50, scrollHeight: 9000 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	let calls = 0;
	let release = null;
	API = {
		getSession: () => {
			calls++;
			return new Promise(resolve => {
				release = () => resolve({ messages: new Array(423).fill(0), total: 923 });
			});
		},
	};
	const jump = jumpToMessage(800);
	const more = loadMoreMessages();
	// Both derived offset 500 from the loaded count: one shared request.
	assert.equal(calls, 1);
	release();
	await Promise.all([jump, more]);
	assert.equal(STATE.messages.length, 923);
	assert.equal(STATE.sessionTotal, 923);
	assert.equal(STATE.loadingMore, false);
	assert.deepEqual(focused, [800]);
	assert.deepEqual(alerts, []);
});

test('a jump beyond the loaded range refreshes the footer/status', async () => {
	resetPaging();
	list = { scrollTop: 0, scrollHeight: 500 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	const calls = [];
	API = {
		getSession: async (sid, from) => {
			calls.push([sid, from]);
			return { messages: from === 500 ? new Array(423).fill(0) : [], total: 923 };
		},
	};
	await jumpToMessage(2000);
	// offset 500 brings the rest, offset 923 is empty (and stops the loop).
	assert.deepEqual(calls, [[240, 500], [240, 923]]);
	assert.equal(STATE.messages.length, 923);
	assert.deepEqual(focused, []);
	// The loaded count moved: the status/footer must reflect it.
	assert.deepEqual(renders, [true]);
});

// ── capture adoption ───────────────────────────────────────────────────

test('a page in flight when a live capture is adopted is dropped', async () => {
	resetPaging();
	list = { scrollTop: 0, scrollHeight: 500 };
	el = () => list;
	STATE = { sessionViewId: 240, sessionTotal: 923, loadingMore: false,
		messages: new Array(500).fill(0) };
	API = {
		getSession: async () => {
			// checkConnection adopted another client's capture meanwhile.
			STATE.sessionViewId = null;
			STATE.currentSessionName = null;
			STATE.currentSessionRawName = null;
			STATE.messages = [];
			STATE.sessionTotal = 0;
			STATE.loadingMore = false;
			return { messages: new Array(423).fill(0), total: 923 };
		},
	};
	await loadMoreMessages();
	assert.equal(STATE.sessionViewId, null);
	assert.equal(STATE.messages.length, 0);
	assert.equal(STATE.sessionTotal, 0);
	assert.deepEqual(alerts, []);
});

// ── the footer ─────────────────────────────────────────────────────────

test('the footer renders only for a saved session with more pages', () => {
	const body = extractFunc(src, 'renderMessages');
	assert.match(body, /if \(STATE\.sessionViewId !== null && STATE\.messages\.length < STATE\.sessionTotal\)/);
	assert.match(body, /<div class="load-more"><button id="load-more-btn">/);
	assert.match(body, /\$\{t\('Load more'\)\} \(\$\{STATE\.messages\.length\} \/ \$\{STATE\.sessionTotal\}\)/);
	// While a page is in flight the button is disabled and labelled.
	assert.match(body, /<button id="load-more-btn" disabled>\$\{t\('Loading…'\)\}<\/button>/);
});

test('the footer is added after the filtered rows', () => {
	const body = extractFunc(src, 'renderMessages');
	const rows = body.indexOf('}).join(\'\');');
	const footer = body.indexOf('load-more-btn');
	assert.ok(rows > 0 && footer > rows,
		'the footer must not be filtered out with the rows');
	assert.match(body, /list\.insertAdjacentHTML\('beforeend', footer\)/);
});

test('the footer button is delegated from the APDU list', () => {
	assert.match(src, /if \(e\.target\.closest\('#load-more-btn'\)\) \{\s*loadMoreMessages\(\);\s*return;/);
});

test('both paging callers go through the shared page request', () => {
	assert.match(src, /const _sessionPageRequests = new Map\(\);/);
	const fetchPage = extractFunc(src, 'fetchSessionPage');
	assert.match(fetchPage, /if \(_sessionPageRequests\.get\(key\) === req\) _sessionPageRequests\.delete\(key\);/);
	assert.match(extractFunc(src, 'loadMoreMessages'), /await fetchSessionPage\(sid, from\)/);
	assert.match(extractFunc(src, 'jumpToMessage'), /await fetchSessionPage\(sid, from\)/);
	// No paging caller still hits the API directly.
	assert.doesNotMatch(extractFunc(src, 'loadMoreMessages'), /API\.getSession/);
	assert.doesNotMatch(extractFunc(src, 'jumpToMessage'), /API\.getSession/);
});

test('the paging state is tracked and reset', () => {
	assert.match(src, /sessionTotal: 0,.*\n.*loadingMore: false,/);
	assert.match(extractFunc(src, 'loadSession'),
		/STATE\.sessionTotal = typeof data\.total === 'number' \? data\.total : data\.messages\.length;/);
	assert.match(extractFunc(src, 'loadSession'), /STATE\.loadingMore = false;/);
	assert.match(extractFunc(src, 'startCapture'), /STATE\.sessionTotal = 0;/);
	assert.match(extractFunc(src, 'startCapture'), /STATE\.loadingMore = false;/);
	assert.match(extractFunc(src, 'stopCapture'), /STATE\.sessionTotal = 0;/);
	assert.match(extractFunc(src, 'stopCapture'), /STATE\.loadingMore = false;/);
	// Adopting another client's capture resets the paged session state too.
	const connect = extractFunc(src, 'checkConnection');
	assert.match(connect, /STATE\.sessionTotal = 0;/);
	assert.match(connect, /STATE\.loadingMore = false;/);
});

test('adopting a live capture drops the viewed saved session', () => {
	const connect = extractFunc(src, 'checkConnection');
	assert.match(connect, /STATE\.sessionViewId = null;/);
	assert.match(connect, /STATE\.currentSessionName = null;/);
	assert.match(connect, /STATE\.currentSessionRawName = null;/);
	assert.match(connect, /el\('session-name-display'\)\.style\.display = 'none';/);
	assert.match(connect, /history\.replaceState\(null, '', location\.pathname\);/);
	// A pending #session=<id> deep link survives the adoption (the first poll
	// may adopt another client's capture before loadSession runs).
	assert.match(connect, /if \(STATE\.deepLinkHandled\) \{\s*try \{ history\.replaceState/);
});

test('a Files-view jump keeps the session total in step', () => {
	assert.match(extractFunc(src, 'jumpToMessage'),
		/if \(typeof data\.total === 'number'\) STATE\.sessionTotal = data\.total;/);
});

test('the footer button has its own styling', () => {
	assert.match(src, /\.load-more \{ display: flex; justify-content: center; padding: 10px 0 6px; \}/);
	assert.match(src, /\.load-more button:hover:not\(:disabled\) \{ border-color: var\(--accent\); color: var\(--accent\); \}/);
	assert.match(src, /\.load-more button:disabled \{ opacity: 0\.5; cursor: default; \}/);
});

test('the READMEs say the views cover only the loaded pages', () => {
	const root = path.join(__dirname, '..', '..');
	assert.match(fs.readFileSync(path.join(root, 'README.md'), 'utf8'),
		/side-panel Stats\/Map views and the command filter count only the pages\s+loaded so far/);
	assert.match(fs.readFileSync(path.join(root, 'README_RUS.md'), 'utf8'),
		/учитывают только\s+загруженные страницы/);
});
