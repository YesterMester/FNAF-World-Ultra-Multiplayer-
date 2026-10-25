import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { WebSocket } from 'ws';
import { createRelay, PROTOCOL } from './server.mjs';

const BUILD = 'a'.repeat(64);
async function setup(t, options = {}) {
  let clock = Date.now();
  const relay = createRelay({ now: () => clock, ...options });
  relay.http.listen(0, '127.0.0.1'); await once(relay.http, 'listening');
  const url = `ws://127.0.0.1:${relay.http.address().port}/lobbies`;
  t.after(() => relay.close());
  const clients = [];
  async function connect(build = BUILD, name = `Player ${clients.length + 1}`, headers = {}) {
    const ws = new WebSocket(url, { headers });
    const messages = []; const waiters = [];
    ws.on('message', (data, binary) => {
      const msg = binary ? Buffer.from(data) : JSON.parse(data);
      const i = waiters.findIndex(w => w.predicate(msg));
      if (i < 0) messages.push(msg);
      else { const [w] = waiters.splice(i, 1); clearTimeout(w.timeout); w.resolve(msg); }
    });
    const c = { ws, send: msg => ws.send(JSON.stringify(msg)),
      next(predicate) {
        if (typeof predicate === 'string') { const type = predicate; predicate = m => m.type === type; }
        const i = messages.findIndex(predicate);
        if (i >= 0) return Promise.resolve(messages.splice(i, 1)[0]);
        return new Promise((resolve, reject) => {
          const w = { predicate, resolve, timeout: setTimeout(() => reject(new Error('Message timeout')), 2500) };
          waiters.push(w);
        });
      } };
    clients.push(c); await once(ws, 'open');
    c.send({ type: 'hello', protocol: PROTOCOL, build, name });
    await c.next('welcome'); await c.next('rooms'); return c;
  }
  return { relay, connect, advance: ms => { clock += ms; } };
}
async function host(c, pin = '') {
  c.send({ type: 'host', name: 'Co-op adventure', pin });
  return (await c.next('hosted')).room;
}
async function join(c, room, pin = '') {
  c.send({ type: 'join', id: room.id, pin }); return c.next('joined');
}

test('open lobbies appear live, host starts, native state and per-player controls are relayed', async t => {
  const { connect } = await setup(t);
  const h = await connect(), guest = await connect();
  const room = await host(h);
  const listing = await guest.next(m => m.type === 'rooms' && m.rooms.length === 1);
  assert.equal(listing.rooms[0].locked, false);
  assert.equal((await join(guest, room)).slot, 1);
  h.send({ type: 'start' }); await guest.next('started');
  const state = Buffer.from([0x53, 1, 0, 0, 0, 0, 0, 0, 1, 10, 20]);
  h.ws.send(state); assert.deepEqual(await guest.next(Buffer.isBuffer), state);
  guest.send({ type: 'input', slot: 0, buttons: 4096, lx: -8000, ly: 1234 });
  assert.deepEqual(await h.next('input'), { type: 'input', slot: 1, buttons: 4096, lx: -8000, ly: 1234 });
});
test('four-digit PIN preserves leading zeros, never appears in listings, and rejects guesses', async t => {
  const { connect } = await setup(t);
  const h = await connect(), guest = await connect(); const room = await host(h, '0042');
  assert.equal(room.locked, true);
  const listing = await guest.next(m => m.type === 'rooms' && m.rooms.length === 1);
  assert.ok(!JSON.stringify(listing).includes('0042'));
  guest.send({ type: 'join', id: room.id, pin: '42' });
  assert.equal((await guest.next('error')).code, 'wrong_pin');
  assert.equal((await join(guest, room, '0042')).slot, 1);
});
test('invalid codes cannot create rooms', async t => {
  const { connect, relay } = await setup(t); const h = await connect();
  for (const pin of ['123', '12345', 'abcd', 1234, null]) {
    h.send({ type: 'host', name: 'Test', pin }); assert.equal((await h.next('error')).code, 'pin');
  }
  assert.equal(relay.rooms.size, 0);
});
test('capacity includes host, build mismatches reject, and only host can start or send world state', async t => {
  const { connect } = await setup(t);
  const h = await connect(), g1 = await connect(), g2 = await connect(), g3 = await connect(), g4 = await connect();
  const other = await connect('b'.repeat(64)); const room = await host(h);
  other.send({ type: 'join', id: room.id, pin: '' }); assert.equal((await other.next('error')).code, 'build');
  await join(g1, room); await join(g2, room); await join(g3, room);
  g4.send({ type: 'join', id: room.id, pin: '' }); assert.equal((await g4.next('error')).code, 'full');
  g1.send({ type: 'start' }); assert.equal((await g1.next('error')).code, 'host_only');
  g1.ws.send(Buffer.alloc(16)); assert.equal((await g1.next('error')).code, 'host_only');
});
test('disconnects clear remote controls, rebalance slots, and remove closed lobbies', async t => {
  const { connect, relay } = await setup(t);
  const h = await connect(), g1 = await connect(), g2 = await connect(); const room = await host(h);
  await join(g1, room); await join(g2, room);
  g1.send({ type: 'leave' }); await g1.next('left'); await h.next('reset-inputs');
  assert.equal((await g2.next(m => m.type === 'members' && m.members.length === 2)).slot, 1);
  h.ws.close(); await g2.next('closed'); assert.equal(relay.rooms.size, 0);
});
test('late joiners receive current state and a running session', async t => {
  const { connect } = await setup(t); const h = await connect(); const room = await host(h);
  h.send({ type: 'start' }); await h.next('started');
  const state = Buffer.from([0x53, 1, 0, 0, 0, 0, 0, 0, 9, 7]); h.ws.send(state);
  const guest = await connect(); await join(guest, room); await guest.next('started');
  assert.deepEqual(await guest.next(Buffer.isBuffer), state);
});
test('wrong PIN guesses are limited across connections from the same address', async t => {
  const { connect, advance } = await setup(t); const h = await connect(), g = await connect();
  const room = await host(h, '9876');
  for (let i = 0; i < 10; i++) {
    g.send({ type: 'join', id: room.id, pin: '0000' }); assert.equal((await g.next('error')).code, 'wrong_pin');
  }
  const g2 = await connect(); g2.send({ type: 'join', id: room.id, pin: '9876' });
  assert.equal((await g2.next('error')).code, 'rate_limit');
  advance(60001); await join(g2, room, '9876');
});
test('invalid inputs and state are rejected without ending a healthy session', async t => {
  const { connect } = await setup(t); const h = await connect(), g = await connect(); const room = await host(h);
  await join(g, room); h.send({ type: 'start' }); await g.next('started');
  g.send({ type: 'input', buttons: -1, lx: 0, ly: 0 }); assert.equal((await g.next('error')).code, 'input');
  h.ws.send(Buffer.alloc(12)); assert.equal((await h.next('error')).code, 'state');
  g.send({ type: 'input', buttons: 0, lx: 0, ly: 0 }); assert.equal((await h.next('input')).slot, 1);
});
test('audio callbacks are limited to valid host-owned events', async t => {
  const { connect } = await setup(t); const h = await connect(), g = await connect(); const room = await host(h);
  await join(g, room); h.send({ type: 'start' }); await g.next('started');
  g.send({ type: 'audio', frame: 4, ids: [1] }); assert.equal((await g.next('error')).code, 'host_only');
  h.send({ type: 'audio', frame: -1, ids: [1] }); assert.equal((await h.next('error')).code, 'audio');
  h.send({ type: 'audio', frame: 4, ids: [1, 3, 5] });
  assert.deepEqual(await g.next('audio'), { type: 'audio', frame: 4, ids: [1, 3, 5] });
});
test('a trusted reverse proxy preserves separate PIN limits for different players', async t => {
  const { connect } = await setup(t, { trustProxy: true });
  const h = await connect(); const room = await host(h, '0042');
  const g = await connect(BUILD, 'First', { 'X-Forwarded-For': '203.0.113.1' });
  for (let i = 0; i < 10; i++) {
    g.send({ type: 'join', id: room.id, pin: '0000' }); assert.equal((await g.next('error')).code, 'wrong_pin');
  }
  const other = await connect(BUILD, 'Second', { 'X-Forwarded-For': '203.0.113.2' });
  await join(other, room, '0042');
});
