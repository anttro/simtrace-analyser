// Scrolling the saved-session APDU list to the end loads the next page
// automatically; the Load more button remains as an explicit fallback.

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractFunc } = require('./helpers.js');

const src = loadSrc();

let STATE = {};
let list = { scrollTop: 0, clientHeight: 0, scrollHeight: 0 };
let loadCalls = 0;
function el() { return list; }
function loadMoreMessages() { loadCalls++; }

eval(
	'const AUTO_LOAD_MARGIN = 200;\n' +
	extractFunc(src, 'maybeLoadMoreOnScroll')
);

function reset(state, geometry) {
	STATE = { sessionViewId: 240, sessionTotal: 2000,
		loadingMore: false, messages: new Array(1500).fill(0), ...state };
	list = { scrollTop: 0, clientHeight: 200, scrollHeight: 1000, ...geometry };
	loadCalls = 0;
}

test('a list scrolled near the bottom loads the next page', () => {
	reset({}, { scrollTop: 700 });   // 700 + 200 >= 1000 - 200
	maybeLoadMoreOnScroll();
	assert.equal(loadCalls, 1);
});

test('a list still above the threshold does not load', () => {
	reset({}, { scrollTop: 500 });   // 500 + 200 < 800
	maybeLoadMoreOnScroll();
	assert.equal(loadCalls, 0);
});

test('live, loading and complete views never auto-load', () => {
	reset({ sessionViewId: null }, { scrollTop: 800 });
	maybeLoadMoreOnScroll();
	assert.equal(loadCalls, 0);

	reset({ loadingMore: true }, { scrollTop: 800 });
	maybeLoadMoreOnScroll();
	assert.equal(loadCalls, 0);

	reset({ messages: new Array(2000).fill(0) }, { scrollTop: 800 });
	maybeLoadMoreOnScroll();
	assert.equal(loadCalls, 0);
});

test('the page size is 2,000 and the scroll listener is wired', () => {
	assert.match(src, /const SESSION_PAGE_SIZE = 2000;/);
	assert.match(src, /limit=\$\{SESSION_PAGE_SIZE\}/);
	assert.match(src, /el\('apdu-list'\)\.addEventListener\('scroll', maybeLoadMoreOnScroll, \{ passive: true \}\);/);
});
