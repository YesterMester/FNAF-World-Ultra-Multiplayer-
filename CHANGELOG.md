# Changelog

## 1.2.0 — 2026-10-26

- Shared four-slot party with four paired reserves, duplicate picks, the full
  categorized roster, locked portraits and clear ownership outlines.
- Independent online roster browsing and validated edits to owned slots only.
  Reset affects the requesting player's entries; supported skins are cosmetic.
- Correct per-slot battle ownership, individual reserve swaps, active health and
  cooldowns, automatic living-reserve replacement and all-party defeat handling.
- Each player's first selected character appears in exploration and side by side
  in NPC conversations. Fit visible sprite bounds rather than transparent canvas.
- Independent online cameras and corrected image/layer/shader replication.
  Guest colliders can activate the original shared world interactions.
- D-pad focus, A select and B back in menus, a controller-friendly online lobby
  with four-digit code entry, and controller editing for Options sliders.
- Separate hooks, ships, platformer actors and Rainbow runners in minigames;
  shared puzzle/stage/results, personal controls and applicable health/respawns.
- Scene-scoped input, release latches and stronger connection recovery. Node
  relays accept active application traffic as a heartbeat.
- Release publication requires a qualification manifest and promotes the exact
  tested Windows/Linux patchers without rebuilding the native extension.

## 1.1.1 — 2026-10-25

- Restore Ultra's original encounter cooldown by preserving object selection in nested game events.
- Route online keyboard input through each copy's assigned player, and clear held movement when changing focus.
- Spawn companions beside player one when co-op starts before entering the overworld.
- Preserve child event boundary markers and the original offline menu keys.

## 1.1.0 — 2026-10-25

- Native online co-op for up to four players, with in-game hosting and lobby discovery.
- Open lobbies or an optional four-digit PIN, late joining and automatic reconnection.
- Correct battle turn ownership, a fresh confirm press for each turn, and matching character and attack graphics across clients.
- Shared Windows and Steam Deck networking builds, plus a Steam Deck desktop launcher.
- Reduced idle network traffic and a configured public lobby service.
- Direct patcher downloads, release checksums and source links on the GitHub page.

## 1.0.0 — 2026-10-25

- Combined FNaF World Ultra and the Local Multiplayer mod in a graphical patcher.
- Added local controller co-op, shared battle turns and independent overworld walkers.
