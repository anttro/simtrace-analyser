// Scrollbar styling: every pane shares one global rule (12px bars, 6px
// rounded thumb) — the APDU list used to be 12px while the side panel,
// detail pane, dialogs and session lists fell back to a 6px default.

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc } = require('./helpers.js');

const src = loadSrc();

test('every pane uses the global 12px scrollbar rule', () => {
	assert.match(src, /::-webkit-scrollbar \{ width: 12px; height: 12px; \}/);
	assert.match(
		src,
		/::-webkit-scrollbar-thumb \{ background: var\(--scrollbar-thumb\); border-radius: 6px; \}/);
	assert.match(src, /::-webkit-scrollbar-track \{ background: var\(--scrollbar-track\); \}/);
});

test('no per-element scrollbar overrides or thin default remain', () => {
	assert.doesNotMatch(src, /\.apdu-list::-webkit-scrollbar/);
	assert.doesNotMatch(src, /\.side-panel::-webkit-scrollbar/);
	assert.doesNotMatch(src, /::-webkit-scrollbar \{ width: 6px/);
});
