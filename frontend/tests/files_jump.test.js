// The Files-view row jump and the APDU list's content-follow decision:
// clicking a timeline row must scroll straight to its APDU — it used to
// render the list with the stick-to-bottom (jump to the end of the trace)
// and then smooth-scroll back up to the record.

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractFunc } = require('./helpers.js');

const src = loadSrc();

let STATE = {};
let API = {};
let renders = [];
let focused = [];
function renderMessages(skipScroll, forceStick) {
	renders.push([skipScroll, forceStick]);
}
function focusMessage(idx) {
	focused.push(idx);
}
eval(
	extractFunc(src, 'jumpToMessage') + '\n' +
	extractFunc(src, 'shouldStickToBottom')
);

test('jumpToMessage pages, renders without stick-to-bottom, then focuses', async () => {
	renders = [];
	focused = [];
	STATE = { sessionViewId: 7, messages: [{}, {}] };
	API = {
		getSession: async (sid, from) => ({
			messages: from === 2 ? [{}, {}, {}] : [],
		}),
	};
	await jumpToMessage(3);
	assert.equal(STATE.messages.length, 5);
	assert.deepEqual(renders, [[true, undefined]]);
	assert.deepEqual(focused, [3]);
});

test('jumpToMessage no-ops without a session view', async () => {
	renders = [];
	focused = [];
	STATE = { sessionViewId: null, messages: [] };
	API = { getSession: async () => { throw new Error('must not fetch'); } };
	await jumpToMessage(3);
	assert.deepEqual(renders, []);
	assert.deepEqual(focused, []);
});

test('shouldStickToBottom: only a reader at the bottom follows new content', () => {
	const list = (scrollTop, clientHeight, scrollHeight) => ({ scrollTop, clientHeight, scrollHeight });
	// At the bottom / within the slack → follow.
	assert.equal(shouldStickToBottom(list(500, 100, 600), false, false), true);
	assert.equal(shouldStickToBottom(list(560, 100, 600), false, false), true);
	// Scrolled up (e.g. after a Files/map jump) → leave the view alone.
	assert.equal(shouldStickToBottom(list(200, 100, 600), false, false), false);
	// An explicit jump never sticks; a new session/capture always does.
	assert.equal(shouldStickToBottom(list(200, 100, 600), true, false), false);
	assert.equal(shouldStickToBottom(list(200, 100, 600), false, true), true);
	// First render: the empty list has no geometry yet.
	assert.equal(shouldStickToBottom(list(0, 0, 0), false, false), true);
});

test('renderMessages scrolls through shouldStickToBottom', () => {
	const body = extractFunc(src, 'renderMessages');
	assert.match(body, /function renderMessages\(skipScroll, forceStick\)/);
	assert.match(body, /const stick = shouldStickToBottom\(list, skipScroll, forceStick\);/);
	assert.match(body, /if \(stick\) list\.scrollTop = list\.scrollHeight;/);
	assert.doesNotMatch(body, /if \(!skipScroll\) list\.scrollTop/);
});

test('jumpToMessage renders with skipScroll (source pin)', () => {
	const body = extractFunc(src, 'jumpToMessage');
	assert.match(body, /renderMessages\(true\);/);
	assert.match(body, /focusMessage\(idx\);/);
});

test('a new session/capture lands at the bottom (source pins)', () => {
	assert.match(extractFunc(src, 'loadSession'), /renderMessages\(false, true\);/);
	assert.match(extractFunc(src, 'startCapture'), /renderMessages\(false, true\);/);
});
