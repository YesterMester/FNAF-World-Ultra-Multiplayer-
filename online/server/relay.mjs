import { createHmac } from 'node:crypto';

// Lobby rules shared by the Node service (server.mjs) and the Cloudflare Worker
// (worker.mjs). This service only forwards game state and controls. Every
// player runs the game.
export const PROTOCOL = 2;
export const MAX_STATE = 2 * 1024 * 1024;
export const CAPACITY = 4;
const MAX_BUFFERED = 4 * MAX_STATE;
const fail = (code, message) => Object.assign(new Error(message), { code });
const utcDay = t => new Date(t).toISOString().slice(0, 10);
export const randomHex = bytes => Array.from(crypto.getRandomValues(new Uint8Array(bytes)),
  b => b.toString(16).padStart(2, '0')).join('');
const same = (a, b) => {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
};
const label = (value, max) => typeof value === 'string' && !!value.trim() && value.trim().length <= max &&
  !/[\x00-\x1f]/.test(value);

// Adapters supply each peer as { ip, send(text), sendBinary(bytes), buffered(),
// close(code, reason), save(state) }. save() lets a hibernating host rebuild
// rooms later through restore().
export function createLobby({ now = Date.now, secret = randomHex(32), graceMs = 30000,
  dailyMessages = Infinity, usage = null, saveUsage = () => {}, maxRooms = 256,
  pinAttempts = [], savePinAttempts = () => {} } = {}) {
  const rooms = new Map();
  const peers = new Set();
  const attempts = new Map(pinAttempts);
  let today = usage?.day === utcDay(now()) ? { day: usage.day, messages: usage.messages } : { day: utcDay(now()), messages: 0 };
  const sign = (id, build, member, role) => createHmac('sha256', secret).update(`${build}:${id}:${member}:${role}`).digest('hex');
  const hashPin = (id, pin) => createHmac('sha256', secret).update(`pin:${id}:${pin}`).digest('hex');
  const send = (p, msg) => { if (!p.away) p.send(JSON.stringify(msg)); };
  const listing = room => ({
    id: room.id, name: room.name, players: room.members.length,
    capacity: CAPACITY, locked: !!room.pinHash, playing: room.playing, build: room.build,
  });
  const save = p => p.save({ ip: p.ip, build: p.build, name: p.name, member: p.member, slot: p.slot,
    room: p.room && { id: p.room.id, name: p.room.name, build: p.room.build, pinHash: p.room.pinHash,
      playing: p.room.playing, host: p.room.host } });
  function browse(p) {
    send(p, { type: 'rooms', rooms: [...rooms.values()]
      .filter(r => r.build === p.build && !r.members[0].away).map(listing) });
  }
  function publish() { for (const p of peers) if (p.build && !p.room) browse(p); }
  function members(room) {
    const list = room.members.map((m, slot) => ({ id: m.member, slot, name: m.name, ...(m.away ? { away: true } : {}) }));
    room.members.forEach((p, slot) => {
      p.slot = slot; save(p);
      send(p, { type: 'members', room: listing(room), slot, members: list });
    });
    publish();
  }
  function leave(p) {
    const room = p.room;
    if (!room) return;
    clearTimeout(p.awayTimer);
    p.room = null; p.away = false; save(p);
    if (room.members[0] === p) {
      rooms.delete(room.id);
      for (const member of room.members.slice(1)) {
        clearTimeout(member.awayTimer);
        member.room = null; save(member);
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
    if (attempts.size >= 1024) for (const [ip, entry] of attempts) if (now() - entry.start >= 60000) attempts.delete(ip);
    let entry = attempts.get(p.ip);
    if (!entry || now() - entry.start >= 60000) {
      if (!entry && attempts.size >= 1024) throw fail('rate_limit', 'The lobby service is busy. Try again shortly.');
      entry = { start: now(), count: 0 }; attempts.set(p.ip, entry);
    }
    if (entry.count >= 10) throw fail('rate_limit', 'Too many code attempts. Wait a minute.');
    ++entry.count; savePinAttempts([...attempts]);
  }
  function capacity() {
    if (today.messages < dailyMessages) return;
    const reset = Date.parse(today.day + 'T00:00:00Z') + 86400000 - now();
    const hours = Math.floor(reset / 3600000), minutes = Math.ceil((reset % 3600000) / 60000);
    throw fail('busy', `Online play has reached today's free limit. New games open again in ${hours} h ${minutes} min.`);
  }
  function seat(p, room, member, type) {
    const role = room.members[0] === p ? 'host' : 'guest';
    p.member = member;
    send(p, { type, room: listing(room), slot: room.members.indexOf(p), member, token: sign(room.id, room.build, member, role) });
  }
  function catchUp(room, p) {
    send(p, { type: 'started' });
    if (room.members[0] === p) return;
    if (room.state) p.sendBinary(room.state);
    send(room.members[0], { type: 'need-state' });
  }
  function resume(p, msg) {
    const role = msg.host ? 'host' : 'guest';
    if (typeof msg.room !== 'string' || !/^[a-f0-9]{24}$/.test(msg.room) || typeof msg.member !== 'string' ||
        !/^[a-f0-9]{16}$/.test(msg.member) || !same(msg.token, sign(msg.room, p.build, msg.member, role))) {
      throw fail('resume', 'That session has ended.');
    }
    let room = rooms.get(msg.room);
    if (!room) {
      // The service restarted. The host's copy recreates the room and guests rejoin it.
      if (role === 'guest') throw fail('resume_wait', 'Waiting for the host to reconnect...');
      const h = msg.host;
      if (!label(h.name, 40) || typeof h.pin !== 'string' || (h.pin !== '' && !/^[0-9]{4}$/.test(h.pin))) {
        throw fail('resume', 'That session has ended.');
      }
      if (rooms.size >= maxRooms || [...rooms.values()].filter(r => r.members[0].ip === p.ip).length >= 4) {
        throw fail('capacity', 'The lobby service is busy. Try again shortly.');
      }
      room = { id: msg.room, name: h.name.trim(), build: p.build,
        pinHash: h.pin ? hashPin(msg.room, h.pin) : null, host: msg.member,
        members: [], playing: h.playing === true, state: null };
      rooms.set(room.id, room);
    }
    const index = room.members.findIndex(m => m.member === msg.member);
    if (index >= 0) {
      const old = room.members[index];
      clearTimeout(old.awayTimer);
      if (!old.away) { old.replaced = true; peers.delete(old); old.close(4000, 'Replaced by a new connection'); }
      room.members[index] = p;
    } else if (role === 'host') {
      if (room.host !== msg.member || room.members.length) throw fail('resume', 'That session has ended.');
      room.members.push(p);
    } else {
      if (room.members.length >= CAPACITY) throw fail('full', 'That lobby is full.');
      room.members.push(p);
    }
    p.room = room;
    seat(p, room, msg.member, 'resumed');
    members(room);
    if (room.playing) catchUp(room, p);
    if (role === 'host') for (const m of room.members.slice(1)) send(m, { type: 'notice', message: 'The host is back.' });
  }
  function handle(p, msg) {
    if (!msg || typeof msg !== 'object' || Array.isArray(msg)) throw fail('message', 'Invalid message.');
    if (msg.type === 'hello') {
      if (p.build) throw fail('hello', 'Already connected.');
      if (msg.protocol !== PROTOCOL) throw fail('version', 'Update the game to join online.');
      if (typeof msg.build !== 'string' || !/^[a-f0-9]{64}$/.test(msg.build)) throw fail('build', 'Invalid game build.');
      if (!label(msg.name, 24)) throw fail('name', 'Use a player name between 1 and 24 characters.');
      p.build = msg.build; p.name = msg.name.trim(); save(p);
      send(p, { type: 'welcome', protocol: PROTOCOL }); browse(p); return;
    }
    if (!p.build) throw fail('hello', 'Connect before using the lobby.');
    switch (msg.type) {
      case 'browse': browse(p); break;
      case 'host': {
        if (p.room) throw fail('room', 'Leave your current session first.');
        if (rooms.size >= maxRooms || [...rooms.values()].filter(r => r.members[0].ip === p.ip).length >= 4) {
          throw fail('capacity', 'The lobby service is busy. Try again shortly.');
        }
        if (!label(msg.name, 40)) throw fail('room_name', 'Use a lobby name between 1 and 40 characters.');
        if (typeof msg.pin !== 'string' || (msg.pin !== '' && !/^[0-9]{4}$/.test(msg.pin))) {
          throw fail('pin', 'Leave the code empty or enter exactly four digits.');
        }
        capacity();
        const id = randomHex(12);
        const room = { id, name: msg.name.trim(), build: p.build, pinHash: msg.pin ? hashPin(id, msg.pin) : null,
          host: randomHex(8), members: [p], playing: false, state: null };
        rooms.set(room.id, room); p.room = room;
        seat(p, room, room.host, 'hosted'); members(room); break;
      }
      case 'join': {
        if (p.room) throw fail('room', 'Leave your current session first.');
        const room = rooms.get(msg.id);
        if (!room || room.members[0].away) throw fail('missing', 'That lobby has closed.');
        if (room.build !== p.build) throw fail('build', 'The host has a different game build. Update both copies.');
        if (room.members.length >= CAPACITY) throw fail('full', 'That lobby is full.');
        if (room.pinHash) {
          pinAttempt(p);
          if (typeof msg.pin !== 'string' || !/^[0-9]{4}$/.test(msg.pin) || !same(hashPin(room.id, msg.pin), room.pinHash)) {
            throw fail('wrong_pin', 'That code is incorrect.');
          }
        }
        capacity();
        p.room = room; room.members.push(p);
        seat(p, room, randomHex(8), 'joined');
        members(room);
        if (room.playing) catchUp(room, p);
        break;
      }
      case 'resume':
        if (p.room) throw fail('room', 'Leave your current session first.');
        resume(p, msg); break;
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
        if ((msg.frame !== undefined && (!Number.isInteger(msg.frame) || msg.frame < 0 || msg.frame > 255)) ||
            (msg.epoch !== undefined && (!Number.isInteger(msg.epoch) || msg.epoch < 0 || msg.epoch > 0x7fffffff))) {
          throw fail('input', 'Invalid input scene.');
        }
        send(p.room.members[0], { type: 'input', slot: p.slot,
          buttons: msg.buttons, lx: msg.lx, ly: msg.ly,
          ...(msg.frame === undefined ? {} : { frame: msg.frame }),
          ...(msg.epoch === undefined ? {} : { epoch: msg.epoch }) }); break;
      }
      case 'party-edit': {
        if (!p.room?.playing || p.room.members[0] === p) throw fail('input', 'Join a running session first.');
        if (msg.version !== 1 || !['pick', 'reset', 'skin'].includes(msg.command) ||
            !Number.isInteger(msg.seq) || msg.seq < 1 || msg.seq > 0x7fffffff ||
            !Number.isInteger(msg.epoch) || msg.epoch < 1 || msg.epoch > 0x7fffffff ||
            !Number.isInteger(msg.revision) || msg.revision < 0 || msg.revision > 0x7fffffff ||
            !Number.isInteger(msg.row) || msg.row < 1 || msg.row > 8 ||
            !Number.isInteger(msg.character) || msg.character < 0 || msg.character > 4096) {
          throw fail('party', 'Invalid party selection.');
        }
        if (msg.seq <= (p.partySequence || 0)) throw fail('party', 'That selection has already been received.');
        p.partySequence = msg.seq;
        send(p.room.members[0], { type: 'party-edit', version: 1, member: p.member, slot: p.slot,
          seq: msg.seq, epoch: msg.epoch, revision: msg.revision, command: msg.command,
          row: msg.row, character: msg.character });
        break;
      }
      case 'party-result': {
        if (!p.room?.playing || p.room.members[0] !== p) throw fail('host_only', 'Only the host confirms party changes.');
        if (!Number.isInteger(msg.seq) || msg.seq < 1 || typeof msg.accepted !== 'boolean' ||
            typeof msg.message !== 'string' || msg.message.length > 160) throw fail('party', 'Invalid party confirmation.');
        const recipient = p.room.members.find(m => m.member === msg.member);
        if (recipient && recipient !== p) send(recipient, { type: 'party-result', seq: msg.seq,
          accepted: msg.accepted, message: msg.message });
        break;
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
  function count() {
    const day = utcDay(now());
    if (day !== today.day) { today = { day, messages: 0 }; saveUsage(today); }
    if (++today.messages % 1000 === 0) saveUsage(today);
  }
  return {
    rooms, peers,
    open(p) {
      Object.assign(p, { build: null, name: '', member: null, room: null, slot: -1, away: false,
        budgetAt: now(), messages: 0, stateAt: -Infinity });
      peers.add(p); save(p);
    },
    message(p, data, binary) {
      if (!peers.has(p)) return;
      count();
      if (now() - p.budgetAt >= 1000) { p.budgetAt = now(); p.messages = 0; }
      if (++p.messages > 100) { p.close(1008, 'Too many messages'); return; }
      try {
        if (binary) {
          if (!p.room?.playing || p.room.members[0] !== p) throw fail('host_only', 'Only the host sends world state.');
          if (data.length < 9 || data[0] !== 0x53 || data.length > MAX_STATE) throw fail('state', 'Invalid world state.');
          if (now() - p.stateAt < 40) return; // cap snapshots at 25 Hz
          p.stateAt = now(); p.room.state = new Uint8Array(data);
          for (const m of p.room.members.slice(1)) {
            if (m.away) continue;
            if (m.buffered() > MAX_BUFFERED) m.close(1013, 'Connection is too slow');
            else m.sendBinary(data);
          }
        } else {
          if (data.length > 4096) throw fail('message', 'Message is too large.');
          handle(p, JSON.parse(typeof data === 'string' ? data : new TextDecoder().decode(data)));
        }
      } catch (e) { send(p, { type: 'error', code: e.code || 'message', message: e.code ? e.message : 'Invalid message.' }); }
    },
    // A clean close (1000) leaves at once. Any other drop keeps the player's
    // seat for graceMs so their game can reconnect and resume.
    close(p, code) {
      if (!peers.delete(p) || p.replaced || !p.room) return;
      if (code === 1000) { leave(p); return; }
      const room = p.room;
      p.away = true;
      p.awayTimer = setTimeout(() => { if (p.away) leave(p); }, graceMs);
      p.awayTimer?.unref?.();
      if (room.members[0] === p) {
        for (const m of room.members.slice(1)) send(m, { type: 'notice', message: 'The host lost connection. Waiting for them to return...' });
      } else send(room.members[0], { type: 'reset-inputs' });
      members(room);
    },
    // Rebuilds players and rooms from save() states after a hibernation wake-up.
    restore(list) {
      const seats = new Map();
      for (const { peer: p, state: s } of list) {
        Object.assign(p, { ip: s.ip, build: s.build, name: s.name, member: s.member, room: null, slot: s.slot ?? -1,
          away: false, budgetAt: now(), messages: 0, stateAt: -Infinity });
        peers.add(p);
        if (!s.room) continue;
        if (!rooms.has(s.room.id)) {
          rooms.set(s.room.id, { ...s.room, members: [], state: null });
          seats.set(s.room.id, []);
        }
        seats.get(s.room.id).push([s.member === s.room.host ? -1 : s.slot, p]);
      }
      for (const [id, list] of seats) {
        const room = rooms.get(id);
        room.members = list.sort((a, b) => a[0] - b[0]).map(([, p]) => p);
        for (const p of room.members) p.room = room;
        if (room.members[0].member !== room.host) {
          rooms.delete(id);
          for (const p of room.members) {
            p.room = null; save(p);
            send(p, { type: 'closed', message: 'The host ended the session.' }); browse(p);
          }
        } else if (room.members.some((p, slot) => p.slot !== slot)) members(room);
      }
    },
    health() {
      return { ok: true, protocol: PROTOCOL, rooms: rooms.size, players: peers.size,
        today: { messages: today.messages, limit: Number.isFinite(dailyMessages) ? dailyMessages : null } };
    },
  };
}
