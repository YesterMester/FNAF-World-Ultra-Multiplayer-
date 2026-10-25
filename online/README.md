# Native online co-op

The native online mode gives each player their own running copy of Ultra. The
host owns the simulation and save. Guests send their assigned controller state
and render the host's objects, strings, counters, camera and layers using their
own game assets. No screen stream, controller driver, router forwarding or
player account is needed.

This is a development preview. Do not replace the stable release until the
in-game validation checklist below is complete and a public relay is configured.

## Player flow

1. Open **Online co-op** in the game, or press **F10**. Enter your player name.
   The lobby connects automatically.
2. To host, choose a lobby name. Leave **Code** empty for an open lobby, or enter
   exactly four digits for a locked lobby. Click **Host game**.
3. Friends select the visible lobby and click **Join selected**. Locked lobbies
   require the same four digits, including any leading zero.
4. The host clicks **Start co-op** and chooses/continues their save in the game.
   Players are assigned P1 through P4. Existing controller controls apply.
5. **F10** opens the lobby again. **Leave session** returns a guest to their own
   title screen. Leaving as host closes the lobby for everyone.

Keyboard guests can use WASD/arrows to walk, Z/Enter/Space to confirm, X/Shift
to fire, R to flee, Tab for the map and E to switch parties. The host operates
the game's mouse menus. Each computer contributes one player in native mode;
the existing four-controller local mode remains available outside a session.

## Free public relay

The public relay can run on Cloudflare's **Workers Free** plan, using a
SQLite-backed Durable Object. The WebSocket Hibernation API keeps idle
connections open while the object sleeps; players do not wait for a server to
spin up after 15 minutes. No paid server, database or custom domain is needed.

Free hosting has limits. Cloudflare includes 100,000 Durable Object request
units per day and 13,000 GB-s of duration; incoming WebSocket messages count at
a 20:1 ratio for request billing. Exceeding a free limit can stop operations
until the daily reset. Provider outages and deployments can also interrupt
connections. **This does not guarantee zero downtime.** See the official
[pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)
and [WebSocket hibernation](https://developers.cloudflare.com/durable-objects/best-practices/websockets/) docs.

Deploy from a free Cloudflare account:

```sh
cd online/server
npm ci --ignore-scripts
npm test
npx wrangler login
npx wrangler deploy
```

Keep the account on Workers Free. The supplied `wrangler.jsonc` creates the
SQLite-backed object automatically. Use the displayed `workers.dev` URL with
`wss://` and `/lobbies`, for example `wss://fwum-relay.example.workers.dev/lobbies`.

The free deployment allows eight lobbies and 64 connected players/browsers.
It refuses new rooms/joins after one million incoming messages in a UTC day to
reserve some quota for running games. Running games can still exhaust the
remaining provider quota; this is a capacity cushion, not an uptime guarantee.
`/health` reports the current message count and limit.

Brief disconnections trigger automatic reconnection for up to 25 seconds.
Players retain their seats, and the host sends fresh state when they return.
The relay saves its signing key and private lobby metadata across hibernation.
PIN attempt limits also survive hibernation; PINs are stored as keyed hashes
and never included in public listings. Resume tokens stay in game memory.

Only the host sends world state, and it stops doing so when alone. Guests send
control changes promptly and refresh unchanged controls every 150 ms. This
reduces idle traffic while preserving the host's stuck-input timeout.

Once deployed, set the repository's Actions variable **FWUM_RELAY_URL** to the
public endpoint and rebuild the patchers. Both patchers bundle the same native
extension artifact and server address. Players then use the in-game menu
without configuring a server. Development builds can instead pass
`--relay-url`; existing builds store the address in `FWUM-online.ini` beside
the game executable.

## Local or self-hosted relay

The same lobby rules also run as a small Node 22 service. It holds lobbies and the latest visible
world state in memory. It never downloads, saves or redistributes game assets.
Four-digit codes are checked on the server and are excluded from room listings.

```sh
cd online/server
npm ci --ignore-scripts
npm test
npm start
```

The local endpoint is `ws://127.0.0.1:8787/lobbies`; `/health` reports service
health. For internet play, deploy `online/server/Dockerfile` on a continuously
running host, or run `docker compose up -d --build` with the supplied compose
file. Put a TLS reverse proxy in front of it; `Caddyfile` is an example. The
public endpoint should be `wss://your-hostname/lobbies`.

When using your own reverse proxy, set `TRUST_PROXY=1` and have the proxy replace
the `X-Forwarded-For` header. This keeps player PIN limits separate; the supplied
compose file enables this for its local proxy. Leave it disabled for direct connections.

Use one relay process/replica so all players see the same rooms. WebSocket
connections must be allowed through the proxy. A sleeping web service cannot
keep a session running. The players need only outbound connections to this
service; they do not open inbound game ports.

Once deployed, set the repository's Actions variable **FWUM_RELAY_URL** to that
public endpoint as described above. For reconnection across Node service
restarts, configure a stable private **RELAY_SECRET** environment variable.
Without it, restarts invalidate resume tokens; reconnecting to the same
running process still works. Do not commit the secret.

## Build the extension and game

Windows: run the following from a Visual Studio **x86 Native Tools** prompt:

```sh
python online/build_native.py
python patcher/patch.py --download --out "FNaF World Ultra Multiplayer" --relay-url ws://127.0.0.1:8787/lobbies
```

Linux developers can use a 32-bit MinGW compiler:

```sh
python3 online/build_native.py --compiler /path/to/i686-w64-mingw32-g++
```

The build helper downloads a pinned [Clickteam Windows SDK](https://github.com/clickteam-plugin/windows)
and [nlohmann/json 3.12.0](https://github.com/nlohmann/json/tree/v3.12.0) into
the ignored build folder. No proprietary game files or SDK binaries are committed.
Release builds compile the extension once and share it between Windows and Linux
patchers. The compatibility ID hashes normalized game events/object definitions
and the extension, so different zlib implementations don't split compatible lobbies.

## Validation

Automated checks cover open and locked rooms, exact PIN length/leading zeros,
PIN attempt limits, capacity, build compatibility, host-only state/audio,
assigned input slots, late joins, disconnect cleanup, authenticated resumption,
relay restarts, hibernation, free-capacity limits and malformed packets.
The existing patcher self-test verifies modified game chunks and their checksum.

```sh
npm test --prefix online/server
g++ -std=c++17 -O2 online/native/snapshot_test.cpp -o /tmp/fwum-snapshot-test
/tmp/fwum-snapshot-test
python3 patcher/selftest.py --game "/path/to/Fnaf World Ultra.dat"
```

Before releasing, verify in two real game instances:

- [ ] Create an open lobby and a locked lobby using `0042`; confirm both join flows.
- [ ] Start a new game and continue a host save; verify the guest's save stays intact.
- [ ] Walk independently with two and four players and switch areas together.
- [ ] Complete battles using each player's assigned turns; verify HP, text, party switches and audio.
- [ ] Join an already running session and disconnect a controller/guest without stuck movement.
- [ ] Leave as guest and as host, then reconnect successfully.
- [ ] Complete the above across Windows and Steam Deck over the public WSS endpoint.

Lab checks have verified a real Proton host and guest joining a `0042` lobby
through the local Cloudflare runtime, independent remote walker movement, and
both games automatically resuming their original seats after that relay was
restarted. Text/counter values are checked through the actual Fusion engine.
Full visual equivalence and battles remain unverified; the stock game also
renders black in the current Wine virtual-desktop lab.

For private lab diagnostics, add `diagnostics=C:\path\to\fwum.log` under
`[online]` in `FWUM-online.ini`. It logs frame transitions and snapshot counts;
it does not record PINs or save contents.
