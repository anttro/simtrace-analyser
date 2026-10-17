// Scrollbar styling: the APDU list and the side panel share one rule, so
// their widths cannot drift apart (the side panel used to fall back to the
// global 6px bar while the list uses 12px).

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc } = require('./helpers.js');

const src = loadSrc();

test('the APDU list and the side panel share the 12px scrollbar rule', () => {
	const rule = /\.apdu-list::-webkit-scrollbar,\s*\n\.side-panel::-webkit-scrollbar \{ width: 12px; \}/;
	assert.match(src, rule);
	// the thumb radius pairs with the width (6px = half of 12px)
	assert.match(
		src,
		/\.apdu-list::-webkit-scrollbar-thumb,\s*\n\.side-panel::-webkit-scrollbar-thumb \{ border-radius: 6px; \}/);
});

test('the global scrollbar default stays thin for the other panes', () => {
	assert.match(src, /::-webkit-scrollbar \{ width: 6px; \}/);
});
