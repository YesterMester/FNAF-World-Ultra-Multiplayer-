# Co-op implementation log

## 2026-10-26

- Working branch: `fix/battle-and-party-ownership`; preserve existing changes.
- Plan: `COOP_PLAN.md`. Published baseline is v1.1.1; new work is private.
- Engine: Clickteam Fusion 2.5+. Patch Ultra events and use the 32-bit native
  extension for session input, replication and client presentation.
- References: Ultra download 3.0.9 / title 3.1.0, Local Multiplayer 0.0.4.
- Private source/game inspection and QA tools: `/home/deck/fnaf-research`.
  Private paired installs, evidence and test profiles: `/home/deck/fnaf-lab`.
- Installed game/save: `/home/deck/Games/FNaF World Ultra Multiplayer`.
  Private builds copy this save and change only the private copy.
- Current private module SHA-256:
  `34665d3ffc714d0dab6a21116b7bcabf4f8c10f5a3f3db43a5c5dd8dc63585dc`.
- Patcher format/team-expression checks and 24 relay tests passed previously.
  These do not establish live gameplay correctness.
- Paired games were launched and connected through the private loopback relay.
  A live capture shows the party slot borders, ownership labels, category header
  and locked portraits. Owned-slot and duplicate-selection checks are running.
- Next: finish live party checks; inspect all battle slots and individual
  reserve switching; qualify rendering/camera before implementing NPC lineups.

### Private gameplay results and subsequent work

- Isolated hardware-accelerated test displays now run through headless gamescope.
  Test profiles, prefixes and diagnostics are under `/home/deck/fnaf-lab/automated`.
  Each client has a separate display and Wine prefix, so tests do not move the
  desktop pointer. The private relay uses loopback port 8788; port 8787 remains
  separate from these tests.
- Helpers accept `FWUM_QA_LAB`; roles specify each display/prefix. Native Windows
  client-coordinate input avoids Xwayland decoration/calibration differences.
- Module `b15adc27fdcfe1e490f1360e2c651bd1420644f2aa568999e391cd526e272dba`:
  two real game processes passed owned-slot edits, wrong-owner rejection,
  duplicate choices and locked-choice rejection. Evidence:
  `automated/party-owned-current.json` and `party-owned-identity.log`.
- The same private build passed battle mouse acceptance/rejection on slots 1–4.
  `automated/battle-owned-current.json` records each accepted owner and rejected
  other player. These checks used a private enemy HP fixture to keep the battle open.
- A P2-only movement check moved P2 from X 1821 to 1928, moved only the guest
  camera from X 1421 to 1528, and left P1 and the host camera unchanged.
  Evidence: `automated/independent-camera-current.json` and both screenshots.
- World captures show the guest scene without the reported duplicate image in
  that scenario. Other areas/transitions still require qualification.
- Short world measurements were approximately 21 host / 30 guest ticks per second
  while another two desktop game processes were running. Performance remains open;
  this is not a matched baseline or a passing release performance result.
- One individual swap changed only slot 1 from Freddy to Toy Bonnie, preserving
  the other three actors. A longer idle battle exposed living reserves left unused
  after active deaths and a whole-team arrival counter incompatible with one swap.
- New changes add stable member IDs and frozen encounter ownership, per-slot
  death replacement, and defeat based on all eight health pools. Pure ownership
  and reserve-health checks passed. Latest module:
  `7c17ba3bb615108d1ac7b14bebe9c910cd4b88a8e9992a764ba2e7a464476b23`.
  Its updated paired game build is running; live swap/death checks are next.
- `identity.py` now adds selected primary-character avatars, labels and group
  scenes in Fredbear/creator rooms. These scenes still require visual checks.
  Companion collision/control was extended to all four underground frames.
- Party cards now also include selected-character portraits. The latest card
  layout requires another capture. Independent online browsing, skins, complete
  controller menus and cooperative minigame adapters remain planned work.

### Independent menus, presentation and scene checks

- Subsequent two-process runs also passed the battle/reserve suite with the new
  independent party UI. The latest complete core run before the general menu
  adapter used module `e4c5cd24dacb0f4c747acc9347339533eaa9be1cbbb20f28e7b20c2eb090c876`.
- Personal party objects are drawn locally after world replication. The host
  sends the categorized roster, unlocks, eight selections and per-row revisions.
  Authenticated `party-edit` requests carry the sender, scene epoch and row
  revision; the host rejects wrong owners and stale edits. Public cursor/page
  replication has been removed. Native input is neutral while browsing a party.
- `automated/party-independent-current.json` proves P2 category/cursor changes
  leave P1's page, focus and shared party unchanged.
- `automated/party-commands-current.json` passed both players' own-slot resets,
  restoring all eight entries, invalid-party start rejection, and separate
  cosmetic preferences without changing the selected base character IDs.
  Skin unlocks were granted only in the private test profile. Preferences use
  `FWUM-skins.ini`, separate from progression saves.
- `automated/npc-duplicate-current.json` passed wrong-owner/stale-revision
  rejection, four identical primaries represented by four separate actors on
  both real clients, and removing one actor when a peer leaves during Fredbear.
  Four participants used two real game processes plus two isolated relay peers.
- NPC sizing now measures occupied collision-mask pixels rather than the
  transparent sprite canvas. The four-person group fits beside Fredbear with
  common feet positions and readable player labels. Captures:
  `automated/qa-npc-four-duplicate-p1.png` and `...-p2.png`.
- Module `5e90acf57adb0b335a70f538ec7cdf73c4428099b297798b0e2fa3e3c87e5d44`
  introduced snapshot format 8, scene epochs on controls, and release latches for
  held actions across focus/scene changes. A same-frame restart now resets native
  state using the extension instance's frame marker, not just its numeric frame.
- Short warmed-up world samples with three participants and two real windows
  measured 56.45 host / 56.99 guest loops per second. The final artifact still
  needs matched baseline and movement/stress measurements.
- General D-pad menu targets, per-client focus markers, and an artifact-only
  publication workflow have been added. These additions are not qualified yet.
  The build workflow no longer automatically publishes every main-branch push.
  `tools/promote_release.py` requires a completed qualification manifest and
  verifies the exact CI artifacts before publishing; no manifest exists yet.
- Remaining work includes general/controller lobby coverage, complete local
  controller parity, P2-triggered interactions, independent world panels,
  minigame adapters, broader battle/move cases, and final MSVC qualification,
  installation and publication. Nothing has been published or installed yet.

## Runtime facts to preserve

- Private run `automated/runs/20261026-041315/result.json` passed owned party
  edits and duplicate/locked-pick checks, all four battle input owners, every
  slot switching both ways without replacing other actors, dead-reserve
  rejection, automatic replacement and defeat on both clients. Module SHA-256
  `2a53e71e12d5ab483d3a9e0c02ccd0aaba03bf4667ba7631ac1d0485ff120dd5`;
  game data `3ed4514d71e8ef16ad67bedb90144ad61cf902b3c531b73766dcd324d6c513b4`.
  Long battle checks boosted only private test HP. Further attacks, victory,
  disconnects, controllers and the final MSVC artifact remain unqualified.
- Mixed-team conditions must evaluate a slot's team separately for every
  selected instance. Dynamic variable-index comparisons and flag conditions
  evaluate an index once before filtering; use Compare Expression for these
  checks. This resolved a live failure where a reserve never received a turn.

- Fusion `rh2Mouse` is already in world coordinates; do not add the camera twice.
- Slot instance values come from `parent_handle` for parent type zero, not the
  parser's `instance` field. Runtime `hoHFII` identifies the source instance.
- Native ownership gates must preserve Fusion object selection.
- Team-flag expressions have varying cached object-list indices. Token-aware
  rewriting currently replaces 167 expressions; byte-signature matching missed some.
- Duplicate character choices require separate slot/actor state.
- Render order comes from the actual display sprite, not only `rSpr` metadata.
- Compile inputs must remain unchanged while building the native extension.
- Both release patchers must contain the same qualified MSVC native artifact.

### Controller and minigame continuation (2026-10-26)

- Private XInput fixtures now address each game directory separately. Title,
  Slot 1, Continue and party navigation were driven with A/D-pad. These are
  simulated-controller results on Proton, not physical Windows pad results.
- Fixed a dynamic menu focus fallback that could select Options before file
  buttons appeared. Controller lobby taps now reset their repeat state on
  release. A controller-only coded Host/Join check succeeded with a leading-zero
  test PIN; lobby captures are `automated/qa-controller-lobby-p1.png` and `...p2.png`.
- Source world collision triggers now accept active guest hitboxes while keeping
  the original reward/transition action list singular. Live chest/travel
  qualification remains required.
- Companion events now append outside source event groups, after Ultra's own
  initialization. Reusing the battle frame's insertion index could split a
  nested event tree in another frame. This affects world/underground/clock
  initialization and requires fresh gameplay checks.
- Clock room controls and puzzle selected-object trees have been adapted for
  separate walkers. Rainbow has an initial separate-runner adapter preserving
  source gravity, collision, jumps, per-runner deaths/checkpoint respawns and one
  shared course/result. These adapters remain unqualified pending valid-scene
  input and full outcome checks. An earlier direct clock jump used an invalid
  source puzzle ID and is not passing gameplay evidence.
- Core run `20261026-154204` passed party and all turn owners but exposed attack
  menus positioned beside an outgoing slot-4 actor after a swap. Added explicit
  active-actor guards when opening a turn; the replacement run is in progress.
  Do not treat that failed run as a combat pass.

- The anchored battle menu passed complete core run `20261026-155436` with
  module `bee6289dfbaa2be2fb9335a69591549dc8296518ea94e631e11f163d49ea9ebb`,
  game data `18dca8e8abe7f0b4a4c3a97518ff98b41c5fc33a757911fb3e7716e942ead303`.
  All four turn owners, all reserve directions, dead-reserve rejection,
  replacement and defeat passed. Source tests now also cover token-aware
  participant remapping without altering literal numbers or strings.
- Valid clock puzzle 2 now shows both selected characters; P2 moved from X 128
  to 182 while P1 stayed at X 128. Evidence: `scene-20-independent-current.json`.
  The original puzzle's selected-object child tree is cloned per collider, not
  merged into one ambiguous target selection. Full puzzle outcome checks remain.
- Rainbow independently moved P2 from X 312 to 418 while P1 stayed at X 290;
  both real clients show labeled runners. Evidence:
  `scene-26-independent-current.json` and the corresponding client captures.
  P2 jump testing failed even though horizontal input works. This is an open
  failure; do not call the Rainbow adapter completed. Added opt-in native input
  diagnostics to distinguish input delivery from source-event selection.
- Latest compiled module after those diagnostic fields:
  `2cf7c87d377a13b367c0a9589ac5ad523ce192603aef3970e400f0dcf06bc26b`.
  `party-online-start.py` is rebuilding/restarting the isolated pair for that
  investigation. The installed game/save and public relay remain untouched.

### Rainbow outcomes and relay deployment

- Module `c7a380f213aa87b624962e0e2ed5ff394577d2c5936f21d4a93de54030ce13e8`
  extends capture bounds, camera following and interpolated positions to the
  cooperative clock/Rainbow scenes. Camera following also needs the guest's
  actors included outside the host viewport; changing only the camera routine
  left distant guests missing from snapshots.
- New native `bound_buttons` metadata sets each participant's minigame held and
  pressed flags before the original physics events. In a clear starting lane,
  P2's full jump reached Y 165 while P1 stayed at Y 412. The earlier low-jump
  assertion stood beneath a low platform and was not a valid full-jump test.
- Positive cloned collision conditions bind the participant as the condition
  owner and retain the shared hazard as the target. This passed P2 hazard death
  without moving/killing P1, then checkpoint respawn at X 101.
- `rainbow-checkpoint-finish-current.json` passed a guest reaching checkpoint 1
  (both runners updated), then the guest finishing and both clients entering
  the original Halloween award frame 22.
- `rainbow-team-failure-current.json` passed a fixture with 32 consumed attempts
  followed by a real guest collision: count 33 and both clients returned through
  loading frame 10. The shared failure event now runs outside the solo death
  event's child tree.
- `rainbow-four-seat-current.json` passed independent P3/P4 routing and leaving:
  P3 moved X 334 to 449 without moving others, then P4 moved X 356 to 245.
  This used two real game processes plus two protocol peers. Both real clients
  rendered all four runners. It is not evidence for four real rendering clients.
- All 26 Node/Cloudflare runtime relay tests passed, including the new Worker
  party-request and scene-tagged-input case. Cloudflare account access was
  checked. The public relay had zero rooms/players before deploying the
  compatible update as Worker version `0acc4193-9eb3-421f-9dc8-1130383136cc`.
  Public WSS validation is running. This is a relay update, not a game release.

### Remaining mode adapters and controller continuation

- The public relay WSS check passed authenticated coded Host/Join, shared-party
  request/result forwarding, scene-scoped input and host closure.
- Foxy Fighters now uses separate flight colliders, aircraft, gun helpers, fire
  cooldowns and health for each occupied seat. Waves, bosses, scoring, power-ups
  and the outcome remain shared. Guests wait for the original ready/intro phase
  before spawning beside the lead ship. A first private check demonstrated
  independent guest movement and original allied bullets. Full outcomes remain
  open; an earlier raw-memory health fixture was invalid and has been replaced
  with private commands that invoke the engine's own counter actions.
- Fishing has separate hooks and drops, consumed catches, a shared timer and a
  single return after occupied hooks resolve. FNaF 57 has separate movement,
  jumps, crouch, weapons and health against the shared enemies, plus shared
  upgrades/teleport checkpoint. Foxy.exe has personal movement/lives/pursuers
  and a shared trial advance. These are implementation status, not gameplay
  passes. Their complete child-event boundaries pass the structural audit.
- Controller A enters options-slider editing; Left/Right adjusts through the
  original clamp/settings events; A/B finishes editing. This temporarily changes
  only the engine's mouse expression, restoring it in Finish without moving the
  desktop pointer. Local co-op X/reset now clears only the requesting player's
  slots, and Y/skin uses separate per-seat cosmetic preferences.
- Native module `2b9415f3c3c830df8ff34459b42d8f7026787f0e547cf39f150941885fe74829`
  is in the current isolated pair. All five native logic tests pass. Final exact
  artifact qualification, installation and publication remain pending.

### Outcome checks, four real clients and connection recovery

- Added explicit connection/role/frame checks to the private scenarios. One
  sequence tried to jump during Ultra's loading-frame transition; the fixture
  now waits for a stable scene and retries a transient run-header change. This
  failed fixture is retained in run `20261026-200545-minigames`.
- The private Node relay treated pong as the only heartbeat even while a client
  sent application data. Active messages now keep it alive. Native failed sends
  notify the game before closing WinHTTP handles, with one disconnect notice per
  connection. A blocked receive cannot leave the UI falsely connected. All 27
  relay tests pass, including active traffic without automatic pong. Diagnostics
  now include connected/reconnecting state. Public Worker behavior is unchanged.
- Foxy.exe filtered shared background actions out of copied child events. Empty
  compiled action lists now retain a no-op; structural checks and the patcher
  reject empty action lists. Controller/mouse hit testing chooses the actual
  topmost interactive sprite, preventing the desktop background from taking the
  Foxy.exe icon click.
- Two real clients passed Foxy Fighters independent movement/fire, separate boss
  damage, either player surviving the other's defeat, and group failure return.
  Fishing passed separate movement/drop/result and a shared return. FNaF 57
  passed separate movement/jump, individual deaths, team failure and shared boss
  result. Foxy.exe passed separate movement/lives, guest advances through trials
  2/3/4, shared success and shared failure. Boundary fixtures are identified in
  the private result files; they are not full human course playthroughs.
- Clock puzzle 2 passed guest interaction with the original target layout, one
  shared clock reward, and a subsequent empty failed round with no extra reward.
  Options D-pad/A/B navigation passed slider X 140 to 120 and a clean return.
- `four-real-current.json` passed four independent Windows game processes under
  Proton in four GPU displays/prefixes. Each client rendered four distinct
  duplicate Freddys in frames 19/18/21; all visible heights measured 185 pixels.
  Rainbow P3 moved X 334 to 421 and P4 moved 356 to 472 without moving others.
  Leaving during dialogue removed only that actor. Module:
  `dd79ccc2b713a973fd0d770daad6ffad75c919042f262e8d1d5decb152f969c6`.
- The next source build also arms action release latches after membership/seat
  changes, and clones clock puzzle 4's interaction-loop initiator for guests.
  These changes, local controller reset/skin parity, wider combat/world checks,
  exact MSVC artifacts, final installation and publication remain pending.
- Do not use the old private `prepare-final-install.py`: it restores a lab save.
  Re-read/back up the latest installed profile immediately before installation,
  and preserve it byte for byte while replacing packaged files.

### Packaged-artifact qualification and two follow-up fixes

- Both downloaded patchers from source `c5f0822` built identical game data and
  embedded the exact shared MSVC native module. Both preserved an existing
  private save byte for byte. The first real pair passed independent roster
  pages, explicit slot ownership, duplicate selection and locked selection.
- A private relay fixture delayed a valid skin confirmation by five seconds.
  The host applied the cosmetic, but the guest discarded the late confirmation
  after the three-second UI timeout, leaving its preference unchanged. Skin
  receipts now survive that timeout and scene changes, with bounded pending
  storage and ordered per-character confirmations. Older receipts cannot
  overwrite a newer accepted preference; session release clears the receipts.
- Ultra's original encounter countdown and trigger required P1's moving flag.
  They now accept each occupied moving walker through one logical OR event,
  retaining the original area/timer checks and one countdown per tick.
- Release checksums list the two downloadable patchers. The separately verified
  embedded native hash is a comment, rather than a checksum for an absent asset.
- These fixes require fresh matching patchers and renewed live qualification.
  The earlier candidate is not installed or published.
