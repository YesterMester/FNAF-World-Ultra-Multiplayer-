import { createServer } from 'node:http';
import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { isIP } from 'node:net';
import { WebSocket, WebSocketServer } from 'ws';

export const PROTOCOL = 1;
export const MAX_STATE = 2 * 1024 * 1024;
const MAX_BUFFERED = 4 * MAX_STATE;
const fail = (code, message) => Object.assign(new Error(message), { code });

// This service only forwards game state and controls. Every player runs the game.
export function createRelay({ now = Date.now, heartbeatMs = 15000, trustProxy = false } = {}) {
  const rooms = new Map();
  const attempts = new Map();
  const peers = new Set();
  const http = createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Cache-Control', 'no-store');
    if (req.url !== '/health') { res.writeHead(404); res.end('{}'); return; }
    res.end(JSON.stringify({ ok: true, protocol: PROTOCOL, rooms: rooms.size }));
  });
  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_STATE, perMessageDeflate: false });
  const send = (p, msg) => {
    if (p.ws.readyState === WebSocket.OPEN) p.ws.send(JSON.stringify(msg));
  };
  const listing = room => ({
    id: room.id, name: room.name, players: room.members.length,
    capacity: 4, locked: !!room.pinHash, playing: room.playing, build: room.build,
  });
  function browse(p) {
    send(p, { type: 'rooms', rooms: [...rooms.values()].filter(r => r.build === p.build).map(listing) });
  }
  function publish() { for (const p of peers) if (p.build && !p.room) browse(p); }
  function members(room) {
    room.members.forEach((p, slot) => {
      p.slot = slot;
      send(p, { type: 'members', room: listing(room), slot,
        members: room.members.map((m, i) => ({ slot: i, name: m.name })) });
    });
    publish();
  }
  function leave(p) {
    const room = p.room;
    if (!room) return;
    p.room = null;
    if (room.members[0] === p) {
      rooms.delete(room.id);
      for (const member of room.members.slice(1)) {
        member.room = null;
        send(member, { type: 'closed', message: 'The host ended the session.' });
        browse(member);
      }
    } else {
      room.members = room.members.filter(m => m !== p);
      // Neutralize all controls before assigning any remaining players new slots.
      send(room.members[0], { type: 'reset-inputs' });
      members(room);
    }
    publish();
  }
  function pinAttempt(p) {
    let entry = attempts.get(p.ip);
    if (!entry || now() - entry.start >= 60000) {
      entry = { start: now(), count: 0 }; attempts.set(p.ip, entry);
    }
    if (++entry.count > 10) throw fail('rate_limit', 'Too many code attempts. Wait a minute.');
  }
  function handle(p, msg) {
    if (!msg || typeof msg !== 'object' || Array.isArray(msg)) throw fail('message', 'Invalid message.');
    if (msg.type === 'hello') {
      if (p.build) throw fail('hello', 'Already connected.');
      if (msg.protocol !== PROTOCOL) throw fail('version', 'Update the game to join online.');
      if (typeof msg.build !== 'string' || !/^[a-f0-9]{64}$/.test(msg.build)) throw fail('build', 'Invalid game build.');
      if (typeof msg.name !== 'string' || !msg.name.trim() || msg.name.trim().length > 24 || /[\x00-\x1f]/.test(msg.name)) {
        throw fail('name', 'Use a player name between 1 and 24 characters.');
      }
      p.build = msg.build; p.name = msg.name.trim();
      send(p, { type: 'welcome', protocol: PROTOCOL }); browse(p); return;
    }
    if (!p.build) throw fail('hello', 'Connect before using the lobby.');
    switch (msg.type) {
      case 'browse': browse(p); break;
      case 'host': {
        if (p.room) throw fail('room', 'Leave your current session first.');
        if (rooms.size >= 256 || [...rooms.values()].filter(r => r.members[0].ip === p.ip).length >= 4) {
          throw fail('capacity', 'The lobby service is busy. Try again shortly.');
        }
        if (typeof msg.name !== 'string' || !msg.name.trim() || msg.name.trim().length > 40 || /[\x00-\x1f]/.test(msg.name)) {
          throw fail('room_name', 'Use a lobby name between 1 and 40 characters.');
        }
        if (typeof msg.pin !== 'string' || (msg.pin !== '' && !/^[0-9]{4}$/.test(msg.pin))) {
          throw fail('pin', 'Leave the code empty or enter exactly four digits.');
        }
        const salt = randomBytes(16);
        const room = { id: randomBytes(12).toString('hex'), name: msg.name.trim(),
          build: p.build, salt, pinHash: msg.pin ? scryptSync(msg.pin, salt, 32) : null,
          members: [p], playing: false, state: null };
        rooms.set(room.id, room); p.room = room;
        send(p, { type: 'hosted', room: listing(room), slot: 0 }); members(room); break;
      }
      case 'join': {
        if (p.room) throw fail('room', 'Leave your current session first.');
        const room = rooms.get(msg.id);
        if (!room) throw fail('missing', 'That lobby has closed.');
        if (room.build !== p.build) throw fail('build', 'The host has a different game build. Update both copies.');
        if (room.members.length >= 4) throw fail('full', 'That lobby is full.');
        if (room.pinHash) {
          pinAttempt(p);
          if (typeof msg.pin !== 'string' || !/^[0-9]{4}$/.test(msg.pin) ||
              !timingSafeEqual(room.pinHash, scryptSync(msg.pin, room.salt, 32))) {
            throw fail('wrong_pin', 'That code is incorrect.');
          }
        }
        p.room = room; room.members.push(p);
        send(p, { type: 'joined', room: listing(room), slot: room.members.length - 1 });
        members(room);
        if (room.playing) {
          send(p, { type: 'started' });
          if (room.state) p.ws.send(room.state, { binary: true });
        }
        break;
      }
      case 'start': {
        if (!p.room || p.room.members[0] !== p) throw fail('host_only', 'Only the host can start the session.');
        p.room.playing = true;
        for (const m of p.room.members) send(m, { type: 'started' });
        members(p.room); break;
      }
      case 'input': {
        if (!p.room?.playing || p.room.members[0] === p) throw fail('input', 'Join a running session first.');
        for (const [key, min, max] of [['buttons', 0, 65535], ['lx', -32768, 32767], ['ly', -32768, 32767]]) {
          if (!Number.isInteger(msg[key]) || msg[key] < min || msg[key] > max) throw fail('input', 'Invalid controller state.');
        }
        send(p.room.members[0], { type: 'input', slot: p.slot,
          buttons: msg.buttons, lx: msg.lx, ly: msg.ly }); break;
      }
      case 'audio': {
        if (!p.room?.playing || p.room.members[0] !== p) throw fail('host_only', 'Only the host sends game audio events.');
        if (!Number.isInteger(msg.frame) || msg.frame < 0 || msg.frame > 255 || !Array.isArray(msg.ids) || msg.ids.length > 128 ||
            msg.ids.some(id => !Number.isInteger(id) || id < 0 || id > 65535)) throw fail('audio', 'Invalid game audio event.');
        for (const m of p.room.members.slice(1)) send(m, { type: 'audio', frame: msg.frame, ids: msg.ids });
        break;
      }
      case 'leave': leave(p); send(p, { type: 'left' }); browse(p); break;
      default: throw fail('message', 'Unknown message.');
    }
  }
  http.on('upgrade', (req, socket, head) => {
    if (req.url !== '/lobbies' || peers.size >= 1024) { socket.destroy(); return; }
    wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws, req));
  });
  wss.on('connection', (ws, req) => {
    const forwarded = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
    const ip = trustProxy && isIP(forwarded) ? forwarded : req.socket.remoteAddress;
    const p = { ws, ip, build: null, room: null, slot: -1, alive: true,
      budgetAt: now(), messages: 0, stateAt: -Infinity };
    peers.add(p);
    ws.on('error', () => {});
    ws.on('pong', () => { p.alive = true; });
    ws.on('message', (data, binary) => {
      if (now() - p.budgetAt >= 1000) { p.budgetAt = now(); p.messages = 0; }
      if (++p.messages > 100) { ws.close(1008, 'Too many messages'); return; }
      try {
        if (binary) {
          if (!p.room?.playing || p.room.members[0] !== p) throw fail('host_only', 'Only the host sends world state.');
          if (data.length < 9 || data[0] !== 0x53 || data.length > MAX_STATE) throw fail('state', 'Invalid world state.');
          if (now() - p.stateAt < 40) return; // cap snapshots at 25 Hz
          p.stateAt = now(); p.room.state = Buffer.from(data);
          for (const m of p.room.members.slice(1)) {
            if (m.ws.bufferedAmount > MAX_BUFFERED) m.ws.close(1013, 'Connection is too slow');
            else if (m.ws.readyState === WebSocket.OPEN) m.ws.send(data, { binary: true });
          }
        } else {
          if (data.length > 4096) throw fail('message', 'Message is too large.');
          handle(p, JSON.parse(data.toString()));
        }
      } catch (e) { send(p, { type: 'error', code: e.code || 'message', message: e.code ? e.message : 'Invalid message.' }); }
    });
    ws.on('close', () => { leave(p); peers.delete(p); });
  });
  const heartbeat = setInterval(() => {
    for (const p of peers) {
      if (!p.alive) { p.ws.terminate(); continue; }
      p.alive = false; p.ws.ping();
    }
    for (const [ip, entry] of attempts) if (now() - entry.start > 60000) attempts.delete(ip);
  }, heartbeatMs);
  heartbeat.unref();
  return { http, wss, rooms,
    async close() {
      clearInterval(heartbeat);
      for (const p of peers) p.ws.terminate();
      await new Promise(resolve => wss.close(resolve));
      await new Promise(resolve => http.close(resolve));
    } };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const relay = createRelay({ trustProxy: process.env.TRUST_PROXY === '1' });
  relay.http.listen(Number(process.env.PORT || 8787), process.env.HOST || '0.0.0.0', () => {
    console.log(`FWUM lobby relay listening on ${relay.http.address().port}`);
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => relay.close().then(() => process.exit(0)));
}
