import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createRelay } from './server.mjs';
import { createLobby } from './relay.mjs';
import { build, host, join, players, resume } from './test-client.mjs';

const BUILD = build();
async function setup(t, options = {}) {
  let clock = Date.now();
  const relay = createRelay({ now: () => clock, graceMs: 200, ...options });
  relay.http.listen(0, '127.0.0.1'); await once(relay.http, 'listening');
  const url = `ws://127.0.0.1:${relay.http.address().port}/lobbies`;
  t.after(() => relay.close());
  return { relay, url, ...players(url, t), advance: ms => { clock += ms; } };
}

test('open lobbies appear live, host starts, native state and per-player controls are relayed', async t => {
  const { connect } = await setup(t);
  const h = await connect(), guest = await connect();
  const { room } = await host(h);
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
  const h = await connect(), guest = await connect(); const { room } = await host(h, '0042');
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
  const other = await connect(build('b')); const { room } = await host(h);
  other.send({ type: 'join', id: room.id, pin: '' }); assert.equal((await other.next('error')).code, 'build');
  await join(g1, room); await join(g2, room); await join(g3, room);
  g4.send({ type: 'join', id: room.id, pin: '' }); assert.equal((await g4.next('error')).code, 'full');
  g1.send({ type: 'start' }); assert.equal((await g1.next('error')).code, 'host_only');
  g1.ws.send(Buffer.alloc(16)); assert.equal((await g1.next('error')).code, 'host_only');
});
test('leaving clears remote controls, rebalances slots, and a host closing cleanly removes the lobby', async t => {
  const { connect, relay } = await setup(t);
  const h = await connect(), g1 = await connect(), g2 = await connect(); const { room } = await host(h);
  await join(g1, room); await join(g2, room);
  g1.send({ type: 'leave' }); await g1.next('left'); await h.next('reset-inputs');
  assert.equal((await g2.next(m => m.type === 'members' && m.members.length === 2)).slot, 1);
  h.ws.close(1000); await g2.next('closed'); assert.equal(relay.rooms.size, 0);
});
test('late joiners receive current state and a running session, and the host is asked for fresh state', async t => {
  const { connect } = await setup(t); const h = await connect(); const { room } = await host(h);
  h.send({ type: 'start' }); await h.next('started');
  const state = Buffer.from([0x53, 1, 0, 0, 0, 0, 0, 0, 9, 7]); h.ws.send(state);
  const guest = await connect(); await join(guest, room); await guest.next('started');
  assert.deepEqual(await guest.next(Buffer.isBuffer), state);
  await h.next('need-state');
});
test('wrong PIN guesses are limited across connections from the same address', async t => {
  const { connect, advance } = await setup(t); const h = await connect(), g = await connect();
  const { room } = await host(h, '9876');
  for (let i = 0; i < 10; i++) {
    g.send({ type: 'join', id: room.id, pin: '0000' }); assert.equal((await g.next('error')).code, 'wrong_pin');
  }
  const g2 = await connect(); g2.send({ type: 'join', id: room.id, pin: '9876' });
  assert.equal((await g2.next('error')).code, 'rate_limit');
  advance(60001); await join(g2, room, '9876');
});
test('invalid inputs and state are rejected without ending a healthy session', async t => {
  const { connect } = await setup(t); const h = await connect(), g = await connect(); const { room } = await host(h);
  await join(g, room); h.send({ type: 'start' }); await g.next('started');
  g.send({ type: 'input', buttons: -1, lx: 0, ly: 0 }); assert.equal((await g.next('error')).code, 'input');
  h.ws.send(Buffer.alloc(12)); assert.equal((await h.next('error')).code, 'state');
  g.send({ type: 'input', buttons: 0, lx: 0, ly: 0 }); assert.equal((await h.next('input')).slot, 1);
});
test('audio callbacks are limited to valid host-owned events', async t => {
  const { connect } = await setup(t); const h = await connect(), g = await connect(); const { room } = await host(h);
  await join(g, room); h.send({ type: 'start' }); await g.next('started');
  g.send({ type: 'audio', frame: 4, ids: [1] }); assert.equal((await g.next('error')).code, 'host_only');
  h.send({ type: 'audio', frame: -1, ids: [1] }); assert.equal((await h.next('error')).code, 'audio');
  h.send({ type: 'audio', frame: 4, ids: [1, 3, 5] });
  assert.deepEqual(await g.next('audio'), { type: 'audio', frame: 4, ids: [1, 3, 5] });
});
test('a trusted reverse proxy preserves separate PIN limits for different players', async t => {
  const { connect } = await setup(t, { trustProxy: true });
  const h = await connect(); const { room } = await host(h, '0042');
  const g = await connect(BUILD, 'First', { 'X-Forwarded-For': '203.0.113.1' });
  for (let i = 0; i < 10; i++) {
    g.send({ type: 'join', id: room.id, pin: '0000' }); assert.equal((await g.next('error')).code, 'wrong_pin');
  }
  const other = await connect(BUILD, 'Second', { 'X-Forwarded-For': '203.0.113.2' });
  await join(other, room, '0042');
});
test('a dropped guest keeps their seat and resumes the running session', async t => {
  const { connect } = await setup(t, { graceMs: 5000 });
  const h = await connect(), g1 = await connect(), g2 = await connect(); const { room } = await host(h);
  await join(g1, room); const seat = await join(g2, room);
  assert.match(seat.member, /^[a-f0-9]{16}$/); assert.match(seat.token, /^[a-f0-9]{64}$/);
  h.send({ type: 'start' }); await g2.next('started');
  const state = Buffer.from([0x53, 2, 0, 0, 0, 0, 0, 0, 3, 3]); h.ws.send(state); await g2.next(Buffer.isBuffer);
  g2.ws.terminate(); await h.next('reset-inputs');
  const away = await h.next(m => m.type === 'members' && m.members[2]?.away);
  assert.equal(away.members.length, 3);
  const back = await resume(connect, seat);
  const resumed = await back.next('resumed');
  assert.equal(resumed.slot, 2); assert.equal(resumed.member, seat.member);
  await back.next('started'); assert.deepEqual(await back.next(Buffer.isBuffer), state);
  await h.next('need-state');
  back.send({ type: 'input', buttons: 1, lx: 0, ly: 0 }); assert.equal((await h.next('input')).slot, 2);
});
test('a dropped host is hidden from listings, then resumes with guests still seated', async t => {
  const { connect } = await setup(t, { graceMs: 5000 });
  const h = await connect(), g = await connect(), watcher = await connect();
  const seat = await host(h, '1234'); await join(g, seat.room, '1234');
  h.send({ type: 'start' }); await g.next('started');
  h.ws.terminate();
  await g.next(m => m.type === 'notice' && /lost connection/.test(m.message));
  await watcher.next(m => m.type === 'rooms' && m.rooms.length === 0);
  const back = await resume(connect, seat, BUILD, { host: { name: 'Co-op adventure', pin: '1234', playing: true } });
  assert.equal((await back.next('resumed')).slot, 0);
  await g.next(m => m.type === 'notice' && /back/.test(m.message));
  await watcher.next(m => m.type === 'rooms' && m.rooms.length === 1);
  g.send({ type: 'input', buttons: 2, lx: 0, ly: 0 }); assert.equal((await back.next('input')).slot, 1);
});
test('a host who does not return in time closes the lobby for everyone', async t => {
  const { connect, relay } = await setup(t, { graceMs: 100 });
  const h = await connect(), g = await connect(); const { room } = await host(h); await join(g, room);
  h.ws.terminate(); await g.next('closed');
  assert.equal(relay.rooms.size, 0);
});
test('after a relay restart the host recreates the lobby and guests rejoin it', async t => {
  const secret = 'f'.repeat(64);
  const first = await setup(t, { secret });
  const h = await first.connect(), g = await first.connect();
  const hostSeat = await host(h, '0042'), guestSeat = await join(g, hostSeat.room, '0042');
  h.send({ type: 'start' }); await g.next('started');
  await first.relay.close();
  const second = await setup(t, { secret });
  const early = await resume(second.connect, guestSeat);
  assert.equal((await early.next('error')).code, 'resume_wait');
  const back = await resume(second.connect, hostSeat, BUILD, { host: { name: 'Co-op adventure', pin: '0042', playing: true } });
  assert.equal((await back.next('resumed')).room.id, hostSeat.room.id);
  early.send({ type: 'resume', room: guestSeat.room.id, member: guestSeat.member, token: guestSeat.token });
  assert.equal((await early.next('resumed')).slot, 1);
  await early.next('started'); await back.next('need-state');
});
test('resume tokens cannot be forged or used for another role or build', async t => {
  const { connect } = await setup(t);
  const h = await connect(), g = await connect(); const hostSeat = await host(h); const guestSeat = await join(g, hostSeat.room);
  const attempts = [
    [{ ...guestSeat, token: '0'.repeat(64) }, BUILD, {}],
    [guestSeat, BUILD, { host: { name: 'Stolen', pin: '', playing: false } }],
    [hostSeat, BUILD, {}],
    [guestSeat, build('c'), {}],
  ];
  for (const [seat, b, extra] of attempts) {
    const c = await resume(connect, seat, b, extra); assert.equal((await c.next('error')).code, 'resume');
  }
});
test('after the daily message limit new lobbies are refused but running sessions continue', async t => {
  const { connect } = await setup(t, { dailyMessages: 6 });
  const h = await connect(), g = await connect(); const { room } = await host(h); await join(g, room);
  h.send({ type: 'start' }); await g.next('started');
  const late = await connect(build('d'));
  late.send({ type: 'host', name: 'Too late', pin: '' }); assert.equal((await late.next('error')).code, 'busy');
  g.send({ type: 'input', buttons: 8, lx: 0, ly: 0 }); assert.equal((await h.next('input')).buttons, 8);
});
test('players and lobbies are rebuilt from saved seats after hibernation', async t => {
  const saved = new Map();
  const peer = (name, sent = []) => ({ name, sent, ip: name, send: text => sent.push(JSON.parse(text)), sendBinary: data => sent.push(data),
    buffered: () => 0, close() {}, save(state) { saved.set(name, state); } });
  const first = createLobby({ secret: 's' });
  const h = peer('host'), g = peer('guest'), idle = peer('idle');
  for (const p of [h, g, idle]) first.open(p);
  first.message(h, JSON.stringify({ type: 'hello', protocol: 2, build: BUILD, name: 'H' }));
  first.message(g, JSON.stringify({ type: 'hello', protocol: 2, build: BUILD, name: 'G' }));
  first.message(idle, JSON.stringify({ type: 'hello', protocol: 2, build: BUILD, name: 'I' }));
  first.message(h, JSON.stringify({ type: 'host', name: 'Saved', pin: '0042' }));
  const id = h.sent.find(m => m.type === 'hosted').room.id;
  first.message(g, JSON.stringify({ type: 'join', id, pin: '0042' }));
  first.message(h, JSON.stringify({ type: 'start' }));
  const second = createLobby({ secret: 's' });
  const h2 = peer('host'), g2 = peer('guest'), idle2 = peer('idle');
  second.restore([[g2, 'guest'], [idle2, 'idle'], [h2, 'host']].map(([p, name]) => ({ peer: p, state: saved.get(name) })));
  assert.equal(second.rooms.get(id).members[0], h2); assert.equal(second.rooms.get(id).playing, true);
  assert.equal(h2.sent.length + g2.sent.length, 0);
  second.message(g2, JSON.stringify({ type: 'input', buttons: 5, lx: 0, ly: 0 }));
  assert.deepEqual(h2.sent.at(-1), { type: 'input', slot: 1, buttons: 5, lx: 0, ly: 0 });
  second.message(idle2, JSON.stringify({ type: 'browse' }));
  assert.equal(idle2.sent.at(-1).rooms.length, 1);
  second.message(idle2, JSON.stringify({ type: 'join', id, pin: '0042' }));
  assert.equal(idle2.sent.find(m => m.type === 'joined').slot, 2);
});
test('health reports rooms, players and the day\'s message use', async t => {
  const { connect, relay } = await setup(t, { dailyMessages: 500 });
  const h = await connect(); await host(h);
  const health = await (await fetch(`http://127.0.0.1:${relay.http.address().port}/health`)).json();
  assert.equal(health.rooms, 1); assert.equal(health.players, 1);
  assert.equal(health.today.messages, 2); assert.equal(health.today.limit, 500);
});

test('saved PIN limits survive hibernation without saving the PIN in seat metadata', () => {
  let budgets = [];
  const saved = new Map();
  const peer = ip => ({ ip, sent: [], send(text) { this.sent.push(JSON.parse(text)); }, sendBinary() {},
    buffered: () => 0, close() {}, save(state) { saved.set(ip, structuredClone(state)); } });
  const h = peer('host'), g = peer('guest');
  const first = createLobby({ secret: 'test', savePinAttempts: entries => { budgets = structuredClone(entries); } });
  for (const p of [h, g]) {
    first.open(p); first.message(p, JSON.stringify({ type: 'hello', protocol: 2, build: BUILD, name: p.ip }));
  }
  first.message(h, JSON.stringify({ type: 'host', name: 'Locked', pin: '0042' }));
  const id = h.sent.find(m => m.type === 'hosted').room.id;
  assert.ok(!JSON.stringify([...saved.values()]).includes('0042'));
  for (let i = 0; i < 10; ++i) first.message(g, JSON.stringify({ type: 'join', id, pin: '0000' }));
  const second = createLobby({ secret: 'test', pinAttempts: budgets });
  const h2 = peer('host'), g2 = peer('guest');
  second.restore([h2, g2].map(p => ({ peer: p, state: saved.get(p.ip) })));
  second.message(g2, JSON.stringify({ type: 'join', id, pin: '0042' }));
  assert.equal(g2.sent.at(-1).code, 'rate_limit');
});

test('resuming an old room respects the relay capacity', async t => {
  const secret = 'stable test key';
  const first = await setup(t, { secret });
  const old = await first.connect(); const seat = await host(old);
  await first.relay.close();
  const second = await setup(t, { secret, maxRooms: 1 });
  await host(await second.connect());
  const back = await resume(second.connect, seat, BUILD, { host: { name: 'Old room', pin: '', playing: false } });
  assert.equal((await back.next('error')).code, 'capacity');
  assert.equal(second.relay.rooms.size, 1);
});
