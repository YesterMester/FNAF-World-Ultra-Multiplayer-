# Release qualification

[Version 1.2.0 manifest](releases/1.2.0.json) pins the source commit, successful
CI build and hashes of both downloadable patchers. Publication promotes those
files directly. Subsequent documentation commits and merge builds do not replace
them. [Recorded results](releases/1.2.0-evidence.json) contain compact observations
without game assets, player profiles or credentials.

Both patchers were downloaded and used to build the game. Their embedded MSVC
native modules match byte for byte, and their resulting game data is identical
to the data exercised in the live tests. No private test events were added to
that data. Runtime tests used source `1830296`; the qualified source `c4649af`
only changes documentation, and both final patchers were checked again for
identical game/native output.

## Exercised coverage

| Area | Release-artifact evidence |
|---|---|
| Party | Independent online categories/cursors; explicit slot ownership; duplicate and locked choices; reset only owned slots; invalid Done; skin preference confirmation delayed seven seconds across a scene change |
| Battles | Two real clients: all four slot owners with mouse input, wrong-owner rejection, every reserve pair in both directions, dead-reserve rejection, automatic replacement and defeat. Four real clients: all four owners and individual reserves with keyboard input |
| Exploration | Guest-only movement and encounter countdown; neutral input stops the countdown; guest chest awards ten tokens once; independent camera coordinates; world labels; guest-initiated Fredbear scene |
| NPC presentation | Four real clients each render four distinct duplicate characters in Fredbear, Animdude and creator scenes, with 185-pixel visible heights; leaving during dialogue removes the departing participant |
| Local controllers | Two simulated XInput controllers: title/file/party navigation, P2 duplicate/skin/reset, valid Start, independent walking, Chips/Bytes entry and P2 Back, Options entry and P1 Back |
| Options | D-pad/A enters slider editing, Left/Right adjusts through Ultra's original clamp/settings logic, A/B exits editing, Back returns to exploration |
| Foxy Fighters | Separate movement/fire/health and original boss damage; either participant can survive the other; team failure returns together |
| Fishing | Separate hooks/drop/results and one shared return |
| FNaF 57 | Separate movement/jump/health; individual deaths, team failure and shared boss-success boundary |
| Foxy.exe | Separate movement/lives, guest advances through trials 2–4, shared success and failure boundaries |
| Rainbow | Separate movement/jump/death/checkpoint; guest finish and shared 33rd-death failure; four real clients prove P3/P4 movement does not move the others |
| Clock/office | Guest clock-puzzle 2 and 4 interactions, one shared reward; office remains open at midnight, guest changes the actual shared camera counter, 6 AM returns both clients |
| Connection recovery | Approximately 100 ms added RTT with jitter; five-second interruption resumes in about six seconds; held confirm does not repeat; beyond-grace interruption releases the seat and permits a fresh join; guest progression unchanged |
| Public service | Two real clients discover/join coded `0042` and open lobbies; independent guest movement; connection held beyond the former 30-second Wine keepalive problem; host closure and guest departure handled; guest save unchanged |
| Long session | 30-minute mixed session, 322 observations and 626 readable client samples; no stale diagnostics or unexplained disconnects. Eighteen transient memory reads occurred while frames changed. The deliberate beyond-grace interruption returned the guest to title and was followed by a successful rejoin |
| Packaging/install | Both patchers preserve an existing profile byte for byte. Latest installed profile/settings and desktop launchers backed up; installed game and F10 lobby smoke checked; installed save preserved |
| CI/structure | Five native logic checks; 27 Node/Cloudflare relay tests; Worker dry run; game structure and child-event boundaries checked across all 39 frames |

The local test's first window-focus attempt ran before the game window appeared;
the harness now waits for it. Options deliberately accepts P1 settings actions,
so its Back check uses P1. World movement fixtures use the stock walkable spawn;
an earlier battle-fixture position lies inside an obstacle. These fixture
corrections do not change the released game files.

## Performance and limits

Matched 60-second measurements used two game processes on the same Steam Deck,
with the same settings and scene. Offline averages were 55.49/55.90 FPS; online
averages were 54.70/55.32 FPS. Online median frame times were 17.39/17.32 ms and
95th-percentile times were 24.51/23.91 ms. The measured online averages remain
above 98% of the corresponding offline baseline. The four-process run shares
one Deck's CPU/GPU and is not evidence of four separate machines' performance.

Windows game and patcher executables were exercised under Proton 11 on Linux.
Physical Windows hardware and physical controllers were not qualified. Controller
tests used per-game XInput simulation in isolated test folders; those files are
absent from the release packages and installed game.

Minigame tests include deliberate health, clock, checkpoint and completion
fixtures to reach original outcome events. They are not full manual course
playthroughs. Combat checks sample Ultra's original attacks; they do not cover
every attack/status/character combination. Shared shop/loadout events and ending
scenes retain original rules; every purchase and ending was not played through.
These limits also apply to the broader regression targets in `COOP_PLAN.md`.

Each computer runs and renders its own game. The host simulates shared state and
owns progression. Travel, story, shops, loadout, Options and office tasks use
shared screens; party browsing and online exploration cameras are personal.
The included free relay is subject to provider capacity limits and outages.
