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

test('the P3 row labels Lc and Le', () => {
	assert.match(src, /decoded\.p3_kind === 'le' \? ' · ' \+ t\('Le \(expected response length\)'\)/);
	assert.match(src, /t\('Lc \(command data length\)'\)/);
});

test('the APDU selection is a blue tint in both themes', () => {
	assert.match(src, /\.apdu-entry\.selected \{ background: var\(--selected-bg\); \}/);
	assert.doesNotMatch(src, /\[data-theme="light"\] \.apdu-entry\.selected/);
	// Dark: a blue (not the neutral --bg-input grey that blended with the
	// GET RESPONSE pair rows); light: the established blue-100.
	assert.match(src, /--selected-bg: #1e3a8a;/);
	assert.match(src, /--selected-bg: #dbeafe;/);
	assert.doesNotMatch(src, /--selected-bg: var\(--bg-input\)/);
});

// ── trace topbar layout ────────────────────────────────────────────────

test('the view selector sits over the side panel at the panel width', () => {
	// one layout variable keeps the two the same width
	assert.match(src, /--side-panel-w: 260px;/);
	assert.match(src, /\.side-panel \{ width: var\(--side-panel-w\);/);
	assert.match(src, /\.trace-topbar \.side-view-select \{ width: var\(--side-panel-w\); flex: 0 0 auto; margin-left: auto; margin-right: -16px; \}/);
	// the selector is a topbar control (before the two-column trace area,
	// which keeps it visible while the panel scrolls)
	const topbar = src.indexOf('<div class="trace-topbar">');
	const sel = src.indexOf('id="side-view-select"');
	const main = src.indexOf('<div class="trace-main">');
	assert.ok(topbar >= 0 && topbar < sel && sel < main, 'selector in the topbar');
});

test('the search input is half its previous width', () => {
	assert.match(src, /\.trace-topbar input \{ flex: 0 1 16\.667%;/);
	// a long session name ellipsizes rather than wrapping the now tighter row
	assert.match(src, /\.trace-topbar #session-name-display \{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; \}/);
});

test('the header title carries no UICC prefix', () => {
	assert.match(src, /<div class="header-title"><a href="https:\/\/osmocom\.org\/projects\/baseband\/wiki\/GSMTAP"/);
	assert.doesNotMatch(src, /class="header-title">UICC/);
});
