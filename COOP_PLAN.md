# FNaF World Ultra Multiplayer: co-op completion plan

Updated: 2026-10-27. **Version 1.2.0 release qualification is recorded in
[`qa/releases/1.2.0.json`](qa/releases/1.2.0.json).** The acceptance scenarios below
remain the long-term regression specification; the qualification report states
the exact exercised paths and the limits of that evidence.

## 1. Target, references and current state

Deliver Ultra's content and presentation with easy native online co-op and the
local multiplayer mod's functionality. Players should be able to host, choose
their own characters, explore, fight, talk to NPCs and play minigames together
without another streaming application.

The references have distinct jobs:

| Reference | What it determines |
|---|---|
| The player's requirements below | Ownership, duplicate picks, individual switching, independent online cameras, controller menus and group NPC scenes |
| Ultra download 3.0.9, displaying 3.1.0 in game | Characters, categories, attacks, unlock rules, areas, story, rewards and visual style |
| FNaF World Local Multiplayer 0.0.4 | Existing local co-op behavior, controller coverage and separate player actors; audit its actual events |
| [FNaF World Multiplayer by Sunny_Verified](https://www.roblox.com/games/116192088324578/FNaF-World-Multiplayer) | The requested multiplayer experience; inspect specific behavior before claiming parity |

The Roblox page identifies the intended game. Its description alone does not
establish its combat, dialogue or minigame rules. Ultra remains the source for
content, and the player's explicit changes take priority over reference behavior.

### Evidence baseline

| Area | Current evidence | Coverage limits |
|---|---|---|
| Release files | Both patchers from CI run `40465128131`, source `c4649affbb2a93968051d3841ea3aea22a4322e1`, produce identical tested game data and native module | Windows executable tested under Proton; no physical Windows machine |
| Party editing | Two-client independent categories/cursors, explicit ownership, duplicates, locked picks, reset, invalid Done and delayed skin receipts passed; two local simulated controllers passed | No physical-controller qualification |
| Battle fixes | Two clients passed all four slot owners with mouse input, both reserve directions, dead-reserve rejection, automatic replacement and defeat; four real clients passed owner rejection and individual reserves with keyboard input | Does not exhaust every Ultra attack/status combination |
| Rendering and cameras | Guest walking, independent camera coordinates, world labels and clean scene changes passed; matched 60-second offline/online performance recorded | Four concurrent processes on one Deck are a rendering stress test, not a four-machine performance benchmark |
| NPC lineup | Four real clients rendered four distinct duplicate characters in Fredbear, Animdude and creator scenes; each measured 185 pixels tall; leave-mid-dialogue cleanup passed | Not an exhaustive visual check of every skin |
| Minigames | Two real clients passed personal controls and shared outcome scenarios for flight, fishing, FNaF 57, Foxy.exe and Rainbow; clock puzzles 2/4 and office camera/6 AM return passed | Outcome fixtures are identified; these are not full manual runs of every course |
| Session recovery | Added 100 ms RTT with jitter, five-second resume, held-confirm release, beyond-grace rejoin and a 30-minute mixed session checked | Free public relay capacity and outages remain external limits |
| Automated checks | Patcher structure checks cover all 39 frames; five native logic checks and 27 Node/Cloudflare relay tests pass in CI | Structural checks complement real gameplay evidence |

Use four distinct statuses for each item: **planned**, **implemented**,
**checked in a private game**, and **qualified on the release artifact**.
A source change or a successful compile cannot advance an item to the last two.

## 2. Required player experience

The explicit player requirements are fixed. Details not previously specified,
such as who advances dialogue or when late joins enter a minigame, are working
defaults below. Record any necessary changes after inspecting Ultra's mechanics.

### Hosting and joining

- In-game Host / Find games / Join / Leave, usable with keyboard, mouse or controller.
- Public lobby listings show name, player count, capacity and whether a code is required.
- A lobby is open or protected by exactly four digits, including leading zeros.
  Codes and reconnect credentials never appear in listings or diagnostic output.
- Each person runs their own game. The relay forwards session data; the host's
  computer runs the shared simulation. Assets and rendering stay on each computer.
- Explain incompatible versions, full rooms, incorrect codes, reconnecting and
  unavailable service inside the game. A failed join must leave menus usable.
- Retain the existing free relay setup. Handle outages and capacity limits;
  zero downtime is not a completion promise.

### Party ownership and selection

One shared party contains four active slots and four matching reserves:

| Players | P1 owns | P2 owns | P3 owns | P4 owns |
|---|---|---|---|---|
| 1 | Active 1, 2, 3, 4 | — | — | — |
| 2 | Active 1, 3 | Active 2, 4 | — | — |
| 3 | Active 1, 4 | Active 2 | Active 3 | — |
| 4 | Active 1 | Active 2 | Active 3 | Active 4 |

Reserve N belongs to whoever owns active slot N. More players reduce the number
of slots each person controls; they do not arbitrarily shrink the character roster.

- Keep Ultra's categories, category order, portrait order, names and character
  information. Show locked characters with a visible lock and selection feedback.
- Derive selectable IDs from Ultra's data. Exclude placeholder entries; do not
  impose a 256-character cutoff or hide real characters after that point.
- Show all eight party entries with portraits, names, P1–P4 ownership labels and
  permanent slot boundaries. Make the active/reserve pairing obvious.
- Distinguish the focused portrait, the player's selected slot and other players'
  selected slots. Use labels as well as colors.
- Select a slot, then a character. Only that slot changes. Clicking another
  player's slot must give feedback and must not silently redirect the next pick.
- Allow duplicates across players and reserves. Key battle state by slot and
  actor identity, so duplicate character IDs cannot merge health or control.
- Online players browse categories and move cursors independently. Local players
  have separate focus markers; changing a shared page must not apply another
  player's pending selection.
- The host's save determines unlocked characters and levels. Guests' private
  saves remain untouched. Already valid parties can start without a forced draft.
- Host starts when all eight entries are valid and pending edits are resolved.
  Disable Done with a clear reason when entries are missing or invalid.
- Reset my slots affects only the requesting player. A separate host Reset party
  action requires an explicit confirmation and refreshes everyone's view.
- Preserve Ultra's restrictions on special fixed-party scenarios unless a
  specific adaptation is necessary and documented.

### Exploration, battles and switching

- Each online camera follows its own player's avatar within the shared area.
  Local players share the local-mod camera, with visible off-screen indicators.
- Keep each player's collision and movement independent. Test the underground
  areas as well as the main overworld.
- Normal area exits move the group together with a visible travel transition.
  Players can separate within an area; simultaneous simulation of different
  Ultra frames is outside this implementation.
- Anyone can trigger an eligible encounter or interaction. Resolve simultaneous
  triggers once. Preserve Ultra's encounter timing; movement must not cause an
  encounter every step.
- Every battle turn names its player and slot. Only that owner can select the
  move or target. The host's mouse obeys the same online rule.
- Support Ultra's full move list, including fourth attacks. Holding confirm
  across a turn or scene change must not select a second action.
- Switching exchanges only the acting slot with its matching reserve. Preserve
  the correct character, HP, status and cooldown on each side; leave all other
  slots unchanged. Handle dead or unavailable reserves explicitly.
- Battle RNG, damage, healing, targeting, victory and defeat have one host-owned
  result. Each client displays that result without independently rerolling it.

### First characters, skins and NPC conversations

**Every current player must appear side by side in Fredbear and other NPC
conversations, using that player's first selected character.**

“First character” means the character selected in the lowest-numbered active
slot owned by that player. A temporary battle switch does not change that
identity. An accepted change to that primary party slot does.

- The same identity drives the overworld avatar and NPC lineup.
- Skin is an optional cosmetic choice attached to that character. Show a Skin
  button only when supported variants exist; changing it cannot change stats,
  collisions or ownership. Persist preferences separately from guest game saves.
- Inventory actual walking/idle art and variants. Where walking art is absent,
  document and verify the best available character-specific presentation rather
  than silently giving several characters the same unrelated model.
- Spawn one distinct dialogue actor per current player, in stable P1–P4 order.
  Two players choosing Freddy must produce two Freddys.
- Place their feet on a common line and size/space the group to fit. Keep the NPC,
  dialogue text, choices and buttons unobstructed. Include small player labels.
- Stage the entire current group even when players were standing far apart
  before the conversation. Dead battle characters still retain player identity.
- Any eligible player can initiate the conversation. The initiator advances the
  shared dialogue; the host takes over if the initiator leaves. All clients see
  the same line, branch and outcome.
- Joining, leaving or changing an eligible primary character/skin rebuilds the
  lineup without restarting the conversation or paying its reward again.
- On exit, remove dialogue actors and restore exploration actors, positions,
  collisions, cameras and input. No leftover silhouettes or doubled sprites.
- Apply this rule to Fredbear's dedicated scene, in-world dialogue and other
  talking animatronics. Shop browsing remains personal UI; a shared story
  conversation inside a shop follows the same group-scene rule.

### Controller and focus behavior

D-pad moves between buttons; A selects; B goes back where the game allows it.
Show the focused control. LB/RB can change categories/pages, and Start opens
the menu. Battle attack selection and the individual switch action must have
visible prompts that match the actual bindings.

No modifier chord is required for ordinary menus. Preserve keyboard/mouse use.
A local controller remains assigned to its player when devices reconnect.
Online play currently contributes one player per computer; mixing several local
players into one online client is a separate feature.

Only the focused game consumes keyboard/mouse input during a two-window test.
Focus loss, controller loss, frame changes and connection loss release held
controls. Returning focus must not create an attack, switch or menu confirmation.

## 3. Multiplayer architecture and transition rules

Use the existing host-authoritative engine and migrate one subsystem at a time.
The main architectural correction is to separate shared gameplay from each
client's presentation and menu interaction.

| State | Owner and synchronization rule |
|---|---|
| Party assignments, unlocks, inventory, enemies, encounters and rewards | Host validates changes and sends authoritative state |
| Player movement and actions | Each player sends requests for its assigned actor; host validates and resolves them |
| Camera, menu cursor, open personal panel and video/audio preferences | Local client; host snapshots must not overwrite these |
| Character and skin choices | Player requests a change; host checks ownership/availability and broadcasts the accepted choice |
| Story dialogue, battle, travel and minigame phase | Shared scene identifier, phase and outcome |
| Saved progression | Host save only; each reward/unlock is committed once per event |

Implementation tasks:

1. Give players stable session identities and explicit slot ownership. Compute
   the table above when membership is committed, rather than deriving ownership
   independently from a changing player count on every frame.
2. Preserve a seat during the reconnect grace period. Freeze battle ownership
   for the encounter. After a permanent departure, visibly give abandoned turns
   to the host until ownership can be reassigned at a safe boundary.
   Late battle joins watch the encounter until that boundary.
3. Send meaningful menu/interaction requests with player, target, scene and
   revision information. Reject stale, repeated or wrong-owner requests on the
   host and return useful feedback. Do not depend on the host's cursor position.
4. Separate local UI objects from replicated world objects. Personal browsing
   must not change someone else's page or force the host out of the world.
   Shared loadout or purchase changes are still validated by the host.
5. Add scene lifecycle handling: exploration → encounter/dialogue/minigame →
   result → exploration. Release input at each boundary; clear old object
   mappings; load the new scene before accepting its input.
6. Give rewards and story flags a completion identity. A retransmitted finish,
   reconnect or repeated button press must not duplicate tokens or unlocks.
7. Give late joins a complete roster and scene state before enabling input.
   In dialogue, insert the new participant into the current line's lineup.
   In minigames, apply the mode's checkpoint/join rule.
8. If the host leaves, close the session cleanly and return guests to their own
   title screens. Host migration is not part of this implementation.

Keep transport changes bounded. If the command or snapshot format changes,
version it, check compatibility before joining and test both relay
implementations. Existing object replication can remain where correct, but
local cameras, menu focus and dialogue staging must have deliberate owners.

### Implementation map and regression risks

| Work area | Main code | Checks that prevent another regression |
|---|---|---|
| Party presentation and edits | `patcher/fwump/party.py`, native party handling in `online/native/runtime.cpp` | Correct instance-to-slot mapping, unique cloned object handles, visible outlines and no implicit selection of another slot |
| Battle ownership and reserves | `patcher/fwump/combat.py`, `patcher/fwump/merge.py`, native battle handling | Preserve Fusion's selected-object list; rewrite every relevant team expression, including differing cached object indices; identify actors by slot |
| Controllers and input focus | `online/native/input.hpp`, `online/native/runtime.cpp`, event alternatives in `merge.py` | Correct world/client mouse coordinates, neutral input after focus loss, no held-confirm replay, no double firing from original and added branches |
| Replication, cameras and scenes | `online/native/runtime.cpp`, `snapshot.hpp`, `images.hpp`, `patcher/fwump/online.py` | Original image handles, actual renderer order including static scenery, shader geometry, one camera transform and cleanup of old-scene objects |
| NPC/minigame adapters | Frame-specific patcher helpers wired through `merge.py`/`online.py`, shared native participant state | Extract original single-player assumptions; reuse common identity, ownership, scene and reward handling |
| Lobby and commands | `online/server/`, native transport and lobby code | Both Node and Cloudflare paths enforce the same ownership, compatibility, resume and capacity rules |
| Build and release | `online/build_native.py`, `patcher/selftest.py`, `.github/workflows/build.yml` | Matching event/expression argument counts, unchanged inputs during compilation, exact tested artifact promoted |

Keep frame-specific transformations in small helpers as they grow. The native
runtime coordinates shared state; it should not accumulate a separate ad hoc
ownership rule for every screen. Fail a patch cleanly if a source fingerprint,
required event or native ABI no longer matches instead of emitting a partly
modified game. Re-run the affected gameplay scenario after any hook change.

## 4. Local-mod parity and Ultra coverage inventory

For every row, retain a source event/frame reference, its current implementation
location, the adaptation, an evidence path and any remaining gap. Extract the
inventory from the compiled references instead of recalling behavior from memory.
The private reference dump remains outside the repository; packages contain the
patcher and permitted dependencies, not extracted game content.

Frame numbers below are zero-based Ultra frames.

| Area / frames | Required behavior and adaptation | Implementation and evidence |
|---|---|---|
| Warning, title and file: 0–2 | Controller focus, new/continue, file selection, online entry, release latch | Native focus invokes original actions; local controller-only title/file/party path checked |
| Party: 3 | Full categorized roster, owned slots, duplicates, outlines, independent online browsing | Implemented in `party.py` and native party handlers; two-client and local-controller evidence |
| Overworld/underground: 4–8 | Separate actors, collision, interactions, pause/map/warp, area transitions | Common companion/camera adapters cover these frames; exact-artifact world evidence covers walking, chest/NPC interaction, encounters and camera separation |
| Battles within 4 | Owner turns, all attacks, individual reserve switch, flee, results | Slot-based adapter retains Ultra attacks; two/four-client ownership and reserve scenarios passed; attack matrix remains sampled |
| Game over/loading: 9–10 | Shared outcome, retry/return, no stale controls or old-scene objects | Common scene/epoch handling; defeat, repeated mode returns and expired-session title return checked |
| Loadout: 11 | Chips/bytes, equip limits, remove, unavailable feedback and synchronized committed changes | Original equip actions remain authoritative; common controller targets; controller toolbar entry/Back checked for both views |
| Shops: 12, 35–36 | Browse, prices, buy, insufficient funds, Back, one debit and reward | Original purchase/debit events retained under shared host authority; native focus targets audited; exhaustive purchase combinations not claimed |
| Dialogue: 19 and embedded NPC events | All-player first-character lineup, shared dialogue, correct exit | Shared identity/staging adapter; guest entry and four real duplicate actors checked |
| Clock/creator rooms: 20–21 | Shared puzzle/story state and correct participant representation | Guest clock interactions and single rewards checked; creator lineup checked on four real clients |
| Fishing and other minigames: 14, 23–26, 33–34 | Separate meaningful participation, deaths, retries and one shared result | Personal hook/ship/actor adapters and shared outcomes checked; office shares cameras/tasks; HTU is an existing shared tutorial |
| Endings/cutscenes/results: 13, 15–18, 22, 27–30, 37–38 | Correct group staging where applicable, confirm/back, music, rewards, return | Common replication and original result logic retained; Animdude/creator staging and minigame result boundaries checked, not every ending |
| Options/help: 31–32 | D-pad/A/B, local preferences, legible control prompts | Native focus and slider editing implemented; slider adjustment, edit exit and return checked; settings changes remain host controlled |

Intentional changes from the local mod must remain explicit: four-attack Ultra
menus, duplicate choices, individual reserve switching, independent online
cameras and ownership validation. Copying the controller extension alone does
not satisfy parity.

## 5. Work sequence and exit criteria

Finish each usable slice and verify it before moving dependent systems onto it.
These gates describe implementation order, not separate promises of completion.

### Gate 0 — Reproducible baseline and private test setup

- Pin source inputs, hashes, branch and current native ABI; preserve the existing work.
- Keep the installed game and its latest save separate from all test profiles.
- Restore the private relay and paired game launchers; check health and process
  ownership before sending input. Save useful evidence before optional captures.
- Record the reported failures as repeatable scenarios in section 7.
- Establish a matched, warmed-up performance baseline for two game processes.

**Exit:** the current private build can be launched and inspected repeatedly;
failures can be reproduced without changing the installed save.

### Gate 1 — Party and combat correctness

- Finish the existing slot borders, labels, portrait focus and ownership guards.
- Verify all four active slots and four reserves, including identical characters.
- Resolve per-slot switching, target selection, HP/status restoration and held inputs.
- Cover all-empty and saved parties, locked picks, Reset, Done, Back and reopening.

**Exit:** PARTY-1/2 and BATTLE-1/2 pass with two real game copies. Run slot
ownership checks for one through four participants. Keep this branch private
until the remaining release gates pass.

### Gate 2 — Session ownership and independent client UI

- Implement the stable membership, request validation and scene boundaries in section 3.
- Move personal browsing/focus out of host-replicated state.
- Make membership changes deliberate; preserve reconnect seats and prevent
  another player's inputs from inheriting stale ownership.
- Ensure entering a shared encounter safely closes or suspends personal menus
  without committing an unfinished choice.

**Exit:** two players can browse different categories, edit their own slots and
return to play without moving each other's cursor or changing another slot.
Stale requests, simultaneous purchases and disconnects cannot corrupt state.

### Gate 3 — Rendering, cameras, movement and performance

- Reproduce the guest's transparent duplicate image while genuinely connected.
  Inspect render order, shaders, viewport geometry and scene cleanup.
- Replicate the world visible to every player's camera, including static scenery;
  avoid duplicating locally loaded scenery or host UI.
- Follow each player's avatar, keep HUD fixed to that client's screen, clamp
  cameras at map edges and handle underground transitions.
- Interpolate visual motion while keeping collision and outcomes authoritative.
  Profile object scans, snapshot size, apply cost and frame pacing.
- Recheck keyboard focus and the original encounter cooldown regression.

**Exit:** WORLD-1/2, INPUT-1 and PERF-1 pass. Both screenshots show one correctly
composited scene; the guest can walk beyond the host's view without losing scenery
or moving the host's camera.

### Gate 4 — Player identity and all-player NPC scenes

- Build the character/animation mapping and a single first-character resolver.
- Complete the Fredbear scene first, then every other dialogue entry point.
- Use the same scene staging and cleanup code for duplicate characters,
  participant changes and repeated conversations.
- Complete supported skin selection after basic identity/lineups work; skins
  must not delay verification of the required Fredbear group.

**Exit:** NPC-1/2 passes for 1, 2, 3 and 4 players, including all four choosing the
same character. Every dialogue entry point in the inventory has evidence.

### Gate 5 — Controller menus and remaining local-mod features

- Complete the inventory in section 4, including the online lobby itself.
- Reuse a common focus/activation layer with explicit screen rules rather than
  creating unrelated controller behavior for each menu.
- Add visible prompts, repeat timing, disabled-control feedback and release latches.
- Verify no mouse is required to host/join, load a game, select a party, change
  loadout, purchase, change options and return to exploration.

**Exit:** MENU-1 passes; the parity inventory contains no unexplained missing
feature. Physical-controller results and simulated-input results are distinguished.

### Gate 6 — Cooperative minigames

Use the per-mode design in section 6. Finish entry → participation → death/retry
→ result → return for one mode before claiming another mode is supported.

**Exit:** MINI-1 passes for every claimed mode. Audit unresolved modes until an
explicit, workable participation design exists; controller input routed to one
actor cannot count as multiplayer.

### Gate 7 — Final qualification, installation and publication

Complete section 8 using the exact release artifacts. A playable private test
build is useful progress, but is not the finished published mod.

## 6. Minigame designs and required investigation

The following are working designs. Inspect each mode's real actors, timers,
collision, result calculation and retry events before implementation. Preserve
Ultra's stage content and reward rules; document necessary co-op adaptations.

| Mode | Participation and camera | Death, joining and completion |
|---|---|---|
| Fishing | Separate player hooks/markers and input timing within the shared view; host resolves contested catches | Players can keep participating after a missed catch; calculate one validated team result using the original reward rules |
| Clock rooms | Represent all players and allow owned interactions against one puzzle state | A disconnect cannot reset or strand the puzzle; apply each clock outcome once |
| Foxy Fighters | Separate controllable aircraft and attacks; shared scrolling stage, enemies and waves | Individual damage/death; respawn at an appropriate existing checkpoint or wait for team retry; late joins enter at a safe wave boundary |
| FNaF 57 | Separate controllable actors for movement/shooting, shared stage and checkpoints; use per-player online views where needed | Individual deaths, checkpoint rejoin and a team retry when everyone is out; one stage-completion reward |
| Foxy.exe | Separate participant control within the active trial; shared trial sequence and prompts | Preserve the mode's hazard rules; one failure must not consume another player's input; resolve per-player failure and team retry explicitly |
| Chica's Magic Rainbow | Separate runners, shared authoritative hazards/timer and independent online cameras | Original checkpoint rules govern respawn; the first valid finish completes the team objective and applies the original result/reward once |
| Mediocore Night / HTU | First audit the playable actors, rooms, tasks and controls; choose separate actors or meaningful assigned stations accordingly | Define failure, late join, retry, completion and reward rules before coding; do not invent these from the mode names |

For each mode:

- Record which original events assume a single actor and replace those references
  with participant-specific state. Merely cloning graphics does not add a player.
- Preserve a required minigame character where the mode depends on it; use player
  labels/colors to distinguish participants rather than forcing incompatible skins.
- Test two people acting at once and deliberately separating or disagreeing.
- Test one death, all deaths, leaving, reconnecting, checkpoint entry, success
  and failure. An unavailable participant cannot leave a permanent wait.
- Ensure the reward is consistent on all clients and applied once to the host save.
- Verify that returning restores the exploration party, avatars, camera and controls.
- Do not silently substitute spectating or shared control for a completed co-op mode.

## 7. Acceptance scenarios and evidence

### Core scenarios

| ID | Scenario | Pass condition |
|---|---|---|
| LOBBY-1 | Create open and coded rooms; join with correct/incorrect code, including 0042; full room, incompatible build and unavailable relay | Clear feedback, correct membership, usable retry/leave; no leaked codes |
| PARTY-1 | P2 selects its second owned slot and picks a character; then tries P1's slot; repeat with duplicate picks | Only the explicitly selected owned entry changes; invalid edit gives feedback; duplicate picks remain distinct |
| PARTY-2 | Locked portraits, all categories, late roster IDs, empty/saved parties, reset, Done, Back and reopen | Complete readable roster, visible outlines, correct validation and preserved assignments |
| BATTLE-1 | Each owner completes turns on slots 1–4 using mouse, keys and pad; another player attempts the action; hold confirm through the next turn | Exactly one accepted action by the correct owner; all four attacks and targeting work |
| BATTLE-2 | Switch each slot to reserve and back; use unequal HP, duplicate characters, status effects and a dead reserve | Correct actor/state retained per side; other slots unchanged; invalid switches explained |
| BATTLE-3 | Healing, multi-target moves, damage over time, revival, Mimic, fourth attacks, flee, victory and defeat | One authoritative result, correct animation and ownership, clean return |
| INPUT-1 | Alternate focus between two real windows while moving, selecting and fighting; disconnect/reconnect a controller | Focused window receives keys/mouse; no stuck input, phantom attack or stolen device assignment |
| WORLD-1 | Host stands still while guest walks beyond the host view, crosses scenery and reaches map edges; repeat underground | Own camera, valid collision and complete scenery; host camera unchanged; HUD stays fixed |
| WORLD-2 | Repeated battles, area changes, NPC scenes and late joins | No translucent duplicate frame, stale actors, missing effects or encounter-on-every-step regression |
| NPC-1 | Fredbear with 1–4 players, all different and then all identical first characters; repeat with supported skins | Exactly one visible actor per current player, side by side on every client, correct identity/skin, no obscured text |
| NPC-2 | Guest initiates dialogue; join/leave mid-conversation; initiator disconnects; finish, revisit and return to exploration | Correct lineup and dialogue continuity, single reward, correct control handoff and complete scene cleanup |
| MENU-1 | Controller-only title → host/join → file → party → gameplay → map/loadout/shop/options → return | Visible D-pad focus, A select, B back, accurate prompts; no mouse or modifier chord needed |
| SESSION-1 | Brief interruption, interruption beyond resume grace, late join, permanent guest departure and host closure | Correct seat/control lifecycle, fresh state on resume, no duplicated rewards; guests retain their own saves |
| MINI-1 | Full success and failure/retry cycle for each mode with two real clients; repeat ownership checks for 3–4 | Meaningful separate participation, correct deaths/joins, one reward and usable return |
| SAVE-1 | Complete a battle, dialogue reward, purchase and minigame; save/reload; leave online | Host progress is correct and persistent; unrelated slots/settings and guest saves remain intact |

### Performance and connection conditions

PERF-1 compares the same scenes, graphics settings and two-process workload
before and after connecting. Warm up first and record at least 60 seconds per
exploration, battle and UI scenario.

- At the existing 60 FPS cap, target a median of at least 55 FPS per client and
  a 95th-percentile frame time at or below 33 ms.
- Connected median FPS should remain at least 90% of the matched baseline.
  If Ultra itself misses the absolute target, retain the measured baseline,
  identify the cause and demonstrate no new regression; do not quietly lower settings.
- Record relay traffic, snapshot frequency/size and input-to-visible-response time.
  Personal cursor/focus feedback should appear on the next rendered frame.
- Repeat core ownership/scene checks with approximately 100 ms added RTT,
  ±30 ms jitter, and controlled 5-second and beyond-grace interruptions.
- Complete a 30-minute mixed session with no accumulating duplicate actors,
  stuck turns, crash or sustained increase in object count after scene cleanup.

Two real copies plus two protocol clients can check four-seat routing. They
cannot prove four clients render correctly. Use four real clients for that claim.
Record Windows/Proton and physical/simulated controller coverage separately.

### Reusable test tooling

Extend the existing private launch/control/observe scripts into named scenarios.
Every run should produce a compact result containing source/native/game hashes,
player roles/count, input method, before/after state, screenshots from both
clients and pass/fail reason. Capture state before taking optional screenshots.

Use state assertions for ownership, HP, membership and rewards; use rendered
captures for outlines, NPC placement, camera independence and overlays. Unit
tests should cover risky pure logic and protocol boundaries, not mirror UI code.
Run affected checks first, then the final integrated suite. Preserve failures
as reproducible cases rather than repeatedly changing several systems at once.

## 8. Release, installation and completion

1. Run patcher structural checks on built game data, native input/snapshot/image
   checks and both relay test suites. Audit all 39 frames and the parity inventory.
2. Qualify a full path: host/join → select duplicate characters → explore apart
   → Fredbear group scene → battle and individual switch → full minigame round
   → reconnect → save/load → leave.
3. Build one MSVC native extension and put that exact artifact in both patchers.
   Record source commit, module/game/patcher hashes and compatibility ID.
4. **Keep publication separate from building.** Build CI has no publication
   permissions. The manual promotion workflow requires a committed qualification
   manifest and verifies the source commit, successful CI run and all artifact
   hashes before publishing. It does not rebuild the native extension.
5. Test the downloaded Windows and Linux patchers, their bundled module identity,
   install behavior and the resulting game. Record any unavailable physical
   Windows/controller coverage rather than claiming it.
6. Back up the latest installed game configuration and save immediately before
   updating. Preserve the profile, tokens, progression, personal settings and
   launcher; keep private high-level test profiles out of the installation.
   Preserve the public relay configuration and verify the published build launches.
7. Publish matching patchers, checksums, accurate controls/install instructions,
   supported-mode coverage and concrete known limitations. Audit packages for
   game files, private references, saves and credentials. Preserve existing
   project authorship and credits.
8. Leave the exact published patchers and a working launcher on the computer.
   Retain the previous working install until the replacement has passed its smoke test.

**Finished means:** the requested ownership, menu, camera, NPC and cooperative
gameplay rules pass on the release artifacts; the local-mod inventory has no
unexplained omissions; every claimed minigame has a completed live scenario;
the installed save is preserved; and the published download matches the tested
build. Open or unverified work remains visible and is never relabeled complete.

## Qualification record

Use [the release manifest](qa/releases/1.2.0.json) and
[coverage report](qa/README.md) for the tested source, downloadable-file hashes,
game/native identity, installation checks and concrete validation limits.
The broader scenarios in section 7 remain regression targets; a passing sampled
release check does not establish every possible attack, purchase or ending.
