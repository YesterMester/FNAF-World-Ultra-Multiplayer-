import { createServer } from 'node:http';
import { pathToFileURL } from 'node:url';
import { isIP } from 'node:net';
import { WebSocket, WebSocketServer } from 'ws';
import { createLobby, MAX_STATE, PROTOCOL } from './relay.mjs';

export { MAX_STATE, PROTOCOL };

// Self-hosted relay. The public service runs the same lobby rules on
// Cloudflare (worker.mjs); this one suits LAN parties and development.
export function createRelay({ now = Date.now, heartbeatMs = 15000, trustProxy = false, ...options } = {}) {
  const lobby = createLobby({ now, ...options });
  const sockets = new Map();
  const http = createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Cache-Control', 'no-store');
    if (req.url !== '/health') { res.writeHead(404); res.end('{}'); return; }
    res.end(JSON.stringify(lobby.health()));
  });
  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_STATE, perMessageDeflate: false });
  http.on('upgrade', (req, socket, head) => {
    if (req.url !== '/lobbies' || lobby.peers.size >= 1024) { socket.destroy(); return; }
    wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws, req));
  });
  wss.on('connection', (ws, req) => {
    const forwarded = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
    const open = () => ws.readyState === WebSocket.OPEN;
    const p = {
      ip: trustProxy && isIP(forwarded) ? forwarded : req.socket.remoteAddress, alive: true,
      send: text => { if (open()) ws.send(text); },
      sendBinary: data => { if (open()) ws.send(data, { binary: true }); },
      buffered: () => ws.bufferedAmount,
      close: (code, reason) => ws.close(code, reason),
      save() {},
    };
    sockets.set(p, ws); lobby.open(p);
    ws.on('error', () => {});
    ws.on('pong', () => { p.alive = true; });
    ws.on('message', (data, binary) => lobby.message(p, data, binary));
    ws.on('close', code => { sockets.delete(p); lobby.close(p, code); });
  });
  const heartbeat = setInterval(() => {
    for (const [p, ws] of sockets) {
      if (!p.alive) { ws.terminate(); continue; }
      p.alive = false; ws.ping();
    }
  }, heartbeatMs);
  heartbeat.unref();
  return { http, wss, rooms: lobby.rooms, lobby,
    async close() {
      clearInterval(heartbeat);
      for (const ws of sockets.values()) ws.terminate();
      await new Promise(resolve => wss.close(resolve));
      await new Promise(resolve => http.close(resolve));
    } };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const relay = createRelay({ trustProxy: process.env.TRUST_PROXY === '1', secret: process.env.RELAY_SECRET || undefined });
  relay.http.listen(Number(process.env.PORT || 8787), process.env.HOST || '0.0.0.0', () => {
    console.log(`FWUM lobby relay listening on ${relay.http.address().port}`);
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => relay.close().then(() => process.exit(0)));
}
