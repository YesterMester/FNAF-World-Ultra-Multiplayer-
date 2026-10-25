import { DurableObject } from 'cloudflare:workers';
import { createLobby, randomHex } from './relay.mjs';

// Public relay on Cloudflare Workers. One Durable Object holds every lobby so
// all players see the same rooms. It uses the WebSocket Hibernation API: idle
// connections stay open without keeping the object in memory, and each
// player's seat is saved on their socket so rooms rebuild after a wake-up.
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
});

export class Lobby extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    const sql = ctx.storage.sql;
    sql.exec('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
    const get = key => sql.exec('SELECT value FROM meta WHERE key = ?', key).toArray()[0]?.value;
    const put = (key, value) => sql.exec('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', key, value);
    // Resume tokens must stay valid when Cloudflare restarts the object.
    let secret = get('secret');
    if (!secret) { secret = randomHex(32); put('secret', secret); }
    this.peers = new Map();
    this.lobby = createLobby({
      secret, maxRooms: 8, dailyMessages: Number(env.DAILY_MESSAGE_LIMIT) || 1800000,
      usage: JSON.parse(get('usage') ?? 'null'), saveUsage: usage => put('usage', JSON.stringify(usage)),
      pinAttempts: JSON.parse(get('pin-attempts') ?? '[]'),
      savePinAttempts: attempts => put('pin-attempts', JSON.stringify(attempts)),
    });
    this.lobby.restore(ctx.getWebSockets().flatMap(ws => {
      const state = ws.deserializeAttachment();
      return state ? [{ peer: this.adapt(ws), state }] : [];
    }));
  }
  adapt(ws, ip = '') {
    const peer = {
      ip,
      send: text => { try { ws.send(text); } catch {} },
      sendBinary: data => { try { ws.send(data); } catch {} },
      buffered: () => 0,
      close: (code, reason) => { try { ws.close(code, reason); } catch {} },
      save: state => { try { ws.serializeAttachment(state); } catch {} },
    };
    this.peers.set(ws, peer);
    return peer;
  }
  fetch(request) {
    if (new URL(request.url).pathname === '/health') return json(this.lobby.health());
    if (request.headers.get('Upgrade')?.toLowerCase() !== 'websocket') return json({ error: 'Expected a WebSocket.' }, 426);
    if (this.lobby.peers.size >= 64) return json({ error: 'The lobby service is busy.' }, 503);
    const [client, server] = Object.values(new WebSocketPair());
    this.ctx.acceptWebSocket(server);
    this.lobby.open(this.adapt(server, request.headers.get('CF-Connecting-IP') || ''));
    return new Response(null, { status: 101, webSocket: client });
  }
  webSocketMessage(ws, data) {
    const peer = this.peers.get(ws);
    if (peer) this.lobby.message(peer, typeof data === 'string' ? data : new Uint8Array(data), typeof data !== 'string');
  }
  webSocketClose(ws, code) {
    const peer = this.peers.get(ws);
    this.peers.delete(ws);
    if (peer) this.lobby.close(peer, code);
    try { ws.close(); } catch {}
  }
  webSocketError(ws) { this.webSocketClose(ws, 1006); }
}

export default {
  fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname !== '/lobbies' && pathname !== '/health') return json({}, 404);
    return env.LOBBY.get(env.LOBBY.idFromName('lobby')).fetch(request);
  },
};
