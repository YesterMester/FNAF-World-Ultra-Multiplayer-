# Native online co-op

The native online mode gives each player their own running copy of Ultra. The
host owns the simulation and save. Guests send their assigned controller state
and render the host's objects, strings, counters, camera and layers using their
own game assets. No screen stream, controller driver, router forwarding or
player account is needed.

The official patchers include the public relay address. The relay is deployed at
`wss://fwum-relay.famous-cry.workers.dev/lobbies`; players use the in-game menu
without configuring hosting.

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
It refuses new rooms/joins after 1.8 million incoming messages in a UTC day to
reserve some quota for running games. Running games can still exhaust the
remaining provider quota; this is a capacity cushion, not an uptime guarantee.
`/health` reports the current message count and limit.

Brief disconnections trigger automatic reconnection for up to 25 seconds.
Players retain their seats, and the host sends fresh state when they return.
The relay saves its signing key and private lobby metadata across hibernation.
PIN attempt limits also survive hibernation; PINs are stored as keyed hashes
and never included in public listings. Resume tokens stay in game memory.

Only the host sends world state, and it stops doing so when alone. Guests send
control changes promptly and refresh unchanged controls every 500 ms. Stick
noise inside the movement dead zone is ignored. World state updates every
50 ms during input or battles and every 100 ms while idle. Disconnected controls
are released after one second, and a confirmed disconnect releases them at once.

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
g++ -std=c++17 -O2 online/native/input_test.cpp -o /tmp/fwum-input-test
/tmp/fwum-input-test
g++ -std=c++17 -O2 online/native/images_test.cpp -o /tmp/fwum-images-test
/tmp/fwum-images-test
python3 patcher/selftest.py --game "/path/to/Fnaf World Ultra.dat"
```

Real gameplay testing on a Steam Deck uses two independent Windows game
processes under Proton 11 through Steam Linux Runtime 4. The checks include:

- Open lobbies and locked `0042` lobbies over the public WSS relay.
- Normal new-game setup, host save continuation and guest save preservation.
- Independent walkers and complete battles, with each of P1-P4 confirming their
  own turns. Two additional protocol clients exercise P3/P4 alongside the two
  real game processes; P1 cannot confirm another player's turn with either the
  keyboard or mouse. Held confirm requires a release when a new turn opens,
  party switching preserves ownership, and F9 cannot reassign native seats.
- Late joins, guest leave/rejoin and host closure returning guests to their own title.
- Actual text/counter readback, including newly created objects, negative values
  and signed 32-bit limits. The format checks cover all 39 game frames.
- Connection resumption after a local Cloudflare runtime restart, retaining seats.

The Windows and Linux patchers share one Windows-built native module. Testing on this computer runs the Windows executable through Proton; a separate
physical Windows machine was not available for a hardware cross-play test.

The renderer sends bounded scalar shader state and display geometry, while each
client creates effects and loads textures locally. Music loops, channel volume
and pause state are restored on midgame joins and reconnects. No GPU pointers,
video streams, game assets or save files travel through the relay.

Active sprites use the original file image handles on the wire. Fusion assigns
different compact image-bank indices after frame loads, so sending a host's
runtime index can show an unrelated character or attack on a guest. Each side
translates through its own image-bank tables; snapshot format 6 rejects the old
index-based format. Image mapping checks exercise all 720 permutations of a
client bank plus unloaded and invalid handles.

For private lab diagnostics, add `diagnostics=C:\path\to\fwum.log` under
`[online]` in `FWUM-online.ini`. It logs frame transitions and snapshot counts;
it does not record PINs or save contents.
An optional `state_file=C:\path\to\world.bin` writes a bounded copy of the
local visible state every 250 ms for automated gameplay checks. It uses the
same binary codec as the relay and contains no lobby tokens or PINs. These
diagnostics are disabled unless a local filename is configured.
