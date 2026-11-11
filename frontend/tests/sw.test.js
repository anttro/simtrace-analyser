// The service worker must never intercept API traffic: /api/status is live
// data and /api/sessions/<id>/pcap is a download.  The previous handler cached
// every GET, so the PCAP download was mediated by the worker (the attached
// Windows HAR shows that service-worker path; its network transfer itself was
// fast, so the client/download side is where a stall can hide).

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(
	path.join(__dirname, '..', 'sw.js'), 'utf8');

function loadWorker() {
	const listeners = {};
	const fetched = [];
	const cached = [];
	const self = {
		addEventListener: (type, fn) => { listeners[type] = fn; },
		location: { origin: 'http://127.0.0.1:8081' },
		skipWaiting: () => {},
		clients: { claim: () => Promise.resolve() },
	};
	const caches = {
		open: async () => ({ put: async req => { cached.push(req.url); } }),
		match: async () => null,
		keys: async () => [],
	};
	const fetch = async req => {
		fetched.push(req.url);
		return { clone: () => ({}) };
	};
	vm.runInNewContext(SRC, { self, caches, fetch, URL, console, Promise });
	const dispatch = (url, method = 'GET') => {
		let responded = false;
		listeners.fetch({
			request: { url, method },
			respondWith: () => { responded = true; },
		});
		return responded;
	};
	return { dispatch, fetched, cached };
}

test('the worker bypasses every API request (including the PCAP download)', () => {
	const { dispatch, fetched } = loadWorker();
	for (const url of [
		'http://127.0.0.1:8081/api/status',
		'http://127.0.0.1:8081/api/sessions/1/pcap',
		'http://127.0.0.1:8081/api',
		'http://127.0.0.1:8081/api/sessions/1/files?x=1',
	]) {
		assert.equal(dispatch(url), false, 'API intercepted: ' + url);
	}
	assert.deepEqual(fetched, [], 'the worker fetched an API URL itself');
});

test('the worker still serves static assets network-first', async () => {
	const { dispatch, fetched, cached } = loadWorker();
	assert.equal(dispatch('http://127.0.0.1:8081/index.html'), true);
	assert.deepEqual(fetched, ['http://127.0.0.1:8081/index.html']);
	await new Promise(resolve => setImmediate(resolve));
	assert.deepEqual(cached, ['http://127.0.0.1:8081/index.html']);
});

test('cross-origin requests are left to the browser', () => {
	const { dispatch, fetched } = loadWorker();
	assert.equal(dispatch('https://github.com/anttro/simtrace-analyser'), false);
	assert.deepEqual(fetched, []);
});

test('the API bypass and the v99 cache are pinned', () => {
	assert.match(SRC, /const CACHE = 'simtrace-analyser-v99';/);
	assert.match(SRC, /url\.origin !== self\.location\.origin/);
	assert.match(SRC, /url\.pathname === '\/api' \|\| url\.pathname\.startsWith\('\/api\/'\)/);
	assert.match(SRC, /must go straight to the browser\/download manager/);
});
