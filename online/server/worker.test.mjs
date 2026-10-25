import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join as path } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build, host, join, players, resume } from './test-client.mjs';

// Runs the Cloudflare Worker in workerd, Cloudflare's runtime, through
// `wrangler dev`. Each test uses its own build ID so rooms never mix.
const here = fileURLToPath(new URL('.', import.meta.url));
const wrangler = path(here, 'node_modules/wrangler/bin/wrangler.js');
const persist = mkdtempSync(path(tmpdir(), 'fwum-worker-'));
let port, worker;
const freePort = () => new Promise(resolve => {
  const s = createServer().listen(0, '127.0.0.1', () => { const { port } = s.address(); s.close(() => resolve(port)); });
});
async function start() {
  worker = spawn(process.execPath, [wrangler, 'dev', '--ip', '127.0.0.1', '--port', String(port), '--persist-to', persist,
    '--show-interactive-dev-session=false', '--log-level', 'warn'],
  { cwd: here, env: { ...process.env, WRANGLER_SEND_METRICS: 'false' }, stdio: ['ignore', 'ignore', 'inherit'] });
  for (let i = 0; i < 300; i++) {
    try { if ((await fetch(`http://127.0.0.1:${port}/health`)).ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('wrangler dev did not start');
}
async function stop() { worker.kill('SIGTERM'); await once(worker, 'exit'); }
test.before(async () => { port = await freePort(); await start(); });
test.after(async () => { await stop(); rmSync(persist, { recursive: true, force: true }); });
const url = () => `ws://127.0.0.1:${port}/lobbies`;

test('worker: lobbies, PIN, state, controls and audio pass through the Durable Object', async t => {
  const { connect } = players(url(), t, 5000); const b = build('1');
  const h = await connect(b), g = await connect(b);
  const seat = await host(h, '0042');
  const listing = await g.next(m => m.type === 'rooms' && m.rooms.length === 1);
  assert.ok(!JSON.stringify(listing).includes('0042'));
  g.send({ type: 'join', id: seat.room.id, pin: '1111' }); assert.equal((await g.next('error')).code, 'wrong_pin');
  assert.equal((await join(g, seat.room, '0042')).slot, 1);
  h.send({ type: 'start' }); await g.next('started');
  const state = Buffer.from([0x53, 2, 0, 0, 1, 2, 3, 4, 5, 6, 7]);
  h.ws.send(state); assert.deepEqual(await g.next(Buffer.isBuffer), state);
  g.send({ type: 'input', buttons: 4096, lx: -8000, ly: 1234 });
  assert.deepEqual(await h.next('input'), { type: 'input', slot: 1, buttons: 4096, lx: -8000, ly: 1234 });
  h.send({ type: 'audio', frame: 3, ids: [7] }); assert.deepEqual(await g.next('audio'), { type: 'audio', frame: 3, ids: [7] });
  h.ws.close(1000); await g.next('closed');
});
test('worker: health and unknown paths', async () => {
  const health = await (await fetch(`http://127.0.0.1:${port}/health`)).json();
  assert.equal(health.ok, true); assert.equal(health.protocol, 2); assert.equal(health.today.limit, 1800000);
  assert.equal((await fetch(`http://127.0.0.1:${port}/`)).status, 404);
  assert.equal((await fetch(`http://127.0.0.1:${port}/lobbies`)).status, 426);
});
test('worker: a dropped guest resumes its seat', async t => {
  const { connect } = players(url(), t, 5000); const b = build('2');
  const h = await connect(b), g = await connect(b);
  const { room } = await host(h); const seat = await join(g, room);
  h.send({ type: 'start' }); await g.next('started');
  g.ws.terminate(); await h.next('reset-inputs');
  const back = await resume(connect, seat, b);
  assert.equal((await back.next('resumed')).slot, 1); await back.next('started'); await h.next('need-state');
  h.ws.close(1000); await back.next('closed');
});
test('worker: sessions resume after the relay restarts', async t => {
  const { connect } = players(url(), t, 8000); const b = build('3');
  const h = await connect(b), g = await connect(b);
  const hostSeat = await host(h, '0042'); const guestSeat = await join(g, hostSeat.room, '0042');
  h.send({ type: 'start' }); await g.next('started');
  await stop(); await Promise.all([h.closed, g.closed]); await start();
  const back = await resume(connect, hostSeat, b, { host: { name: 'Co-op adventure', pin: '0042', playing: true } });
  assert.equal((await back.next('resumed')).room.id, hostSeat.room.id);
  const guest = await resume(connect, guestSeat, b);
  assert.equal((await guest.next('resumed')).slot, 1); await guest.next('started'); await back.next('need-state');
  const state = Buffer.from([0x53, 2, 0, 0, 9, 9, 9, 9, 9]);
  back.ws.send(state); assert.deepEqual(await guest.next(Buffer.isBuffer), state);
  back.ws.close(1000); await guest.next('closed');
});
