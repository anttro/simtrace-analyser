// The PWA is one large inline script; a broken comment or expression there
// is a blank/broken UI for every tab.  Compile the whole script so a syntax
// error fails the suite instead of only a browser.

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const HTML = fs.readFileSync(
	path.join(__dirname, '..', 'index.html'), 'utf8');

test('the PWA inline script parses', () => {
	const scripts = [...HTML.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
	assert.ok(scripts.length > 0, 'no inline script found');
	for (const [i, match] of scripts.entries()) {
		assert.doesNotThrow(
			() => new vm.Script(match[1], { filename: 'index.html:script' + i }),
			'inline script ' + i + ' has a syntax error');
	}
});
