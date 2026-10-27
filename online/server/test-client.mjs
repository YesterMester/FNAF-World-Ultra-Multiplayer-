import { once } from 'node:events';
import { WebSocket } from 'ws';
import { PROTOCOL } from './relay.mjs';

// Test players shared by the Node and Cloudflare relay tests.
export const build = (c = 'a') => c.repeat(64);

export function players(url, t, timeoutMs = 2500) {
  const all = [];
  t.after(() => { for (const c of all) c.ws.terminate(); });
  async function open(headers = {}, options = {}) {
    const ws = new WebSocket(url, { ...options, headers });
    const messages = []; const waiters = [];
    ws.on('message', (data, binary) => {
      const msg = binary ? Buffer.from(data) : JSON.parse(data);
      const i = waiters.findIndex(w => w.predicate(msg));
      if (i < 0) messages.push(msg);
      else { const [w] = waiters.splice(i, 1); clearTimeout(w.timeout); w.resolve(msg); }
    });
    const c = { ws, messages, closed: once(ws, 'close'), send: msg => ws.send(JSON.stringify(msg)),
      next(predicate) {
        if (typeof predicate === 'string') { const type = predicate; predicate = m => m.type === type; }
        const i = messages.findIndex(predicate);
        if (i >= 0) return Promise.resolve(messages.splice(i, 1)[0]);
        return new Promise((resolve, reject) => {
          const w = { predicate, resolve, timeout: setTimeout(() => reject(new Error('Message timeout')), timeoutMs) };
          waiters.push(w);
        });
      } };
    all.push(c); await once(ws, 'open'); return c;
  }
  async function connect(b = build(), name = `Player ${all.length + 1}`, headers = {}) {
    const c = await open(headers);
    c.send({ type: 'hello', protocol: PROTOCOL, build: b, name });
    await c.next('welcome'); await c.next('rooms'); return c;
  }
  return { open, connect };
}
export async function host(c, pin = '', name = 'Co-op adventure') {
  c.send({ type: 'host', name, pin }); return c.next('hosted');
}
export async function join(c, room, pin = '') {
  c.send({ type: 'join', id: room.id, pin }); return c.next('joined');
}
// Reconnects a dropped player to the seat it held.
export async function resume(connect, seat, b = build(), extra = {}) {
  const c = await connect(b);
  c.send({ type: 'resume', room: seat.room.id, member: seat.member, token: seat.token, ...extra });
  return c;
}
