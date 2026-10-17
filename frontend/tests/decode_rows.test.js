// ATR/historical rows, the card-capabilities summary and the MANAGE CHANNEL
// response row (server-decoded fields rendered by the detail panel).

const { test } = require('node:test');
const assert = require('node:assert');
const { loadSrc, extractFunc } = require('./helpers.js');

const src = loadSrc();
eval(
	extractFunc(src, 'ifaceValue') + '\n' +
	extractFunc(src, 'atrPpsRows') + '\n' +
	extractFunc(src, 'responseRows')
);

function row(rows, label) {
	const found = rows.find(r => r[0] === label);
	return found ? found[1] : undefined;
}

test('atrPpsRows: COMPACT-TLV historical and card capabilities', () => {
	const rows = atrPpsRows({
		type: 'atr',
		historical: {
			raw: '8031E073FE211B66D0022A761300',
			category: 'COMPACT-TLV objects',
			card_capabilities: {
				raw: 'FE211B', tables: 3,
				max_channels: 4,
				channel_assignment: ['by the card', 'by the interface device'],
			},
			objects: [
				{ tag: '3', name: 'Card service data', value: 'E0' },
				{ tag: '7', name: 'Card capabilities', value: 'FE211B' },
				{ tag: '6', name: 'Pre-issuing data', value: 'D0022A761300' },
			],
		},
	});
	assert.match(row(rows, 'Historical'), /COMPACT-TLV objects/);
	const caps = row(rows, 'Card capabilities');
	assert.match(caps, /logical channels: up to 4/);
	assert.match(caps, /assigned by the card, by the interface device/);
	assert.match(caps, /FE211B/);
	assert.match(row(rows, 'Historical objects'), /Card service data \(E0\)/);
	assert.match(row(rows, 'Historical objects'), /Pre-issuing data/);
});

test('atrPpsRows: "8 or more" logical channels', () => {
	const rows = atrPpsRows({
		type: 'atr',
		historical: {
			raw: '8031E073FE2157',
			category: 'COMPACT-TLV objects',
			card_capabilities: {
				raw: 'FE2157', tables: 3,
				max_channels: '8 or more',
				channel_assignment: ['by the card'],
				extended_lc_le: true,
			},
		},
	});
	const caps = row(rows, 'Card capabilities');
	assert.match(caps, /logical channels: 8 or more/);
	assert.match(caps, /extended Lc\/Le/);
});

test('atrPpsRows: a plain status-indicator historical stays short', () => {
	const rows = atrPpsRows({
		type: 'atr',
		historical: { raw: '808105', category: 'COMPACT-TLV objects',
			life_cycle: 'operational state (activated)' },
	});
	assert.match(row(rows, 'Historical'), /operational state \(activated\)/);
	assert.equal(row(rows, 'Card capabilities'), undefined);
});

test('responseRows: MANAGE CHANNEL assigned channel', () => {
	const html = responseRows({ channel: 5 });
	assert.match(html, /Assigned channel/);
	assert.match(html, /<td class="value">5<\/td>/);
});
