# FNaF World Ultra Multiplayer

**FNaF World Ultra** + **FNaF World Local Multiplayer**, combined: Ultra's 300+ characters,
new areas and attacks, played with controllers and with up to **4 players sharing the battles**.
Works on **Windows** and **Steam Deck**, with local co-op and built-in native
online play for up to **four players**. Open **Online co-op** or press **F10**,
choose **Host game**, and friends can find your lobby in the game. Leave the code
empty for an open game, or protect it with exactly **four digits**.

**Download the latest patcher:**
[Windows](https://github.com/YesterMester/FNAF-World-Ultra-Multiplayer-/releases/latest/download/FWUM-Patcher-Windows.exe) ·
[Steam Deck / Linux](https://github.com/YesterMester/FNAF-World-Ultra-Multiplayer-/releases/latest/download/FWUM-Patcher-Linux-SteamDeck)

The free public lobby service is included in the official patchers. Each player
runs their own copy of the game; the host owns the shared simulation and save.
Each online player has an independent exploration camera and party cursor.
See [online details and testing](online/README.md).

This repository holds a **patcher**, not the games. The patcher downloads both mods from
their official Game Jolt pages (or uses copies you already have) and builds the merged game
on your computer.

| | |
|---|---|
| FNaF World Ultra | download v3.0.9 (in-game title v3.1.0), <https://gamejolt.com/games/FWU/996891> |
| FNaF World Local Multiplayer | v0.0.4, <https://gamejolt.com/games/FWLOCAL/937743> |

---

## What the merged game adds to Ultra

* **Native online co-op:** public lobby browser, hosting, optional four-digit PIN,
  late joining and automatic recovery after brief connection interruptions.
  Each computer contributes one player; no router configuration or player account is needed.

* **A shared party with owned slots.** Four active characters have four paired
  reserves. Duplicate characters are allowed. Ultra's full categorized roster,
  locked portraits and permanent slot outlines stay visible. Online players
  browse independently and edit only their own entries.
* **Individual battle turns and switching.** Only the acting character's owner
  selects its attack or swaps it with its paired reserve. Other slots keep their
  current character, health and cooldown. Disconnected battle turns pass to the
  host after the reconnect grace period.

| Players | P1 controls | P2 controls | P3 controls | P4 controls |
|---|---|---|---|---|
| 1 | 1, 2, 3, 4 | — | — | — |
| 2 | 1, 3 | 2, 4 | — | — |
| 3 | 1, 4 | 2 | 3 | — |
| 4 | 1 | 2 | 3 | 4 |

Each entry includes the same-numbered reserve. Ownership stays fixed during an
online battle; a late join enters the next encounter.

* **Selected-character avatars and NPC groups.** Each player's lowest active
  slot supplies their exploration appearance. All current players stand beside
  one another in Fredbear, Animdude and creator conversations, including duplicate
  picks. Supported skins are optional cosmetics and never change battle stats.
  Characters without dedicated walking art use their own existing idle pose.
* **Exploration together.** Players have separate walkers and online cameras
  within the current area. Eligible chests, NPCs and exits accept guest
  interactions. Battles, travel and story scenes move the group together.
  Local controllers share a camera and stay within its range.
* **Controller menus.** D-pad moves focus; A selects; B returns. Start opens the
  exploration toolbar. The native lobby also supports D-pad/A/B and editing a
  four-digit code, including leading zeros.
* **Cooperative minigames.** Fishing has personal hooks; Foxy Fighters has
  personal ships, fire and health; FNaF 57 has personal movement, jumps, weapons
  and health; Foxy.exe has personal movement/lives and shared trial advances;
  Rainbow has personal runners, jumps, deaths and checkpoint respawns. Clock
  rooms share puzzle progress and allow every participant to interact.
  Mediocore Night uses a shared office/cameras/tasks, with B to leave; a co-op
  round returns at 6 AM. Ultra's HTU screen remains a shared tutorial.

### Controls

| Controller | Keyboard | Does |
|---|---|---|
| Left stick / D-pad | WASD / arrows | Move, focus menu buttons, highlight an attack |
| A | Z / Enter / Space | Select, confirm, jump; drop a fishing hook |
| B | R | Back; hold to flee a battle; next owned slot in the party editor |
| X | X / Shift | Fire; reset your own slots in the party editor |
| Y | C in the party editor | Cycle an unlocked supported skin |
| LB / RB | Q / E in the party editor | Previous / next roster category |
| RB in battle | E | Swap only the acting slot with its paired reserve |
| Start | — | Open the world toolbar; P1 starts a valid party |
| Back / View | Tab | Map while held; P1 leaves the party editor |

In Options, A enters slider editing; Left/Right adjusts; A/B finishes editing.
Release confirm before a new turn or scene. Online play uses one player per
computer. Outside online play, F9 assigns keyboard/mouse to P1 and controllers
to the remaining local players; pressing F9 again restores controller-only play.

Party roster browsing and online cameras are personal. Travel, story, shops,
loadout and Options are shared screens; the host controls save/file/settings
changes. Guests keep their own game saves. Cosmetic preferences are stored
separately in `FWUM-skins.ini`.

---

## Getting it

### Windows

1. Download **`FWUM-Patcher-Windows.exe`** from the
   [Releases page](../../releases/latest).
2. Run it. If Windows SmartScreen warns about an unknown app, click *More info* then *Run anyway*.
3. Leave **"Download both games from Game Jolt for me"** selected (or point it at copies you
   already downloaded), pick where to save, and click **Build**.
   The build needs about 2.5 GB of free space and a few minutes.
4. Open the new **FNaF World Ultra Multiplayer** folder and run **`Fnaf World Ultra.exe`**.

If an Ultra save file (`fnafwf.cfg`) is in your Ultra folder, it is copied over, so your
progress carries on.

### Steam Deck

1. Switch to **Desktop Mode** and download **`FWUM-Patcher-Linux-SteamDeck`** from the
   [Releases page](../../releases/latest).
2. Right-click it, then *Properties → Permissions → Is executable*, and double-click it to run.
3. Build the game as in the Windows steps above. You can also build on a PC and copy the
   folder over.
4. In Desktop Mode, open **`Play Multiplayer.sh`** in the built game folder. It finds
   your installed Proton and its Steam runtime automatically.
5. For Gaming Mode, in Steam (desktop mode): *Games → Add a Non-Steam Game to My Library → Browse*, set the file
   type to *All Files*, and pick `Fnaf World Ultra.exe` in the new folder.
6. Right-click the new entry, then *Properties → Compatibility → Force the use of a specific
   Steam Play compatibility tool* → **Proton Experimental** (or Proton 9).
7. Back in Gaming Mode, start it. The Deck's own controls are **Player 1**. Pair more
   controllers over Bluetooth for Players 2 to 4.

### Any computer with Python 3

```sh
python3 patcher/patch.py --download --out "FNaF World Ultra Multiplayer"
# or, with your own copies:
python3 patcher/patch.py --ultra "path/to/FNaF World Ultra" \
    --mp "path/to/fnaf-world-multiplayer-beta.exe" --out "FNaF World Ultra Multiplayer"
```

Running `python3 patcher/patch.py` with no arguments opens the same window as the
downloadable patcher.

---

## Playing online

1. Everyone builds the game with the same version of the official patcher.
2. Open **Online co-op** or press **F10**, and enter your player name. The lobby
   connects automatically.
3. Host: choose a lobby name, leave **Code** empty or enter exactly four digits,
   and click **Host game**, then **Start co-op**.
4. Friends: select that lobby, enter its code when locked, and click **Join selected**.
   You can join before starting or while the host is already playing.
5. The host starts a new game or continues a save. Guests use their own controller
   or **WASD/arrows**, **Z/Enter** to confirm, **R** to flee, **Tab** for the map,
   and **E** to switch their acting slot with its reserve. Follow the `P#:` prompt for battle turns.
6. **F10 → Leave session** leaves the game. Guests return to their own title screen;
   the host's progress stays on the host's computer.

The shared Cloudflare relay is free and keeps lobby sockets connected while idle.
Free hosting has daily capacity limits and no guarantee of zero downtime. Service
configuration and hosting details are in [online/README.md](online/README.md).


---

## Troubleshooting

* **The controller does nothing.** The game reads Xbox-style (XInput) controllers. PlayStation
  and Switch controllers work through Steam Input (add the game to Steam) or DS4Windows.
  A controller plugged in while the game runs is picked up after a few seconds.
* **A turn won't accept my button.** It's someone else's turn. Look at the `P#:` line at
  the bottom of the screen, then release and press confirm. In online play the
  host's mouse follows the same turn ownership; offline mouse assistance can pick any turn.
* **The patcher says an event wasn't found.** FNaF World Ultra probably updated and moved
  something the patcher hooks into. The patcher stops instead of building a broken game.
  Open an issue, or point the patcher at the tested Ultra version (3.0.9).

---

## How it works

Both mods are Clickteam Fusion 2.5 games without public source. The patcher:

1. reads Ultra's compiled data file (`Fnaf World Ultra.dat`): its chunks, objects, frames
   and event lists (`patcher/fwump/ccn.py`, `patcher/fwump/fusion.py`);
2. adds the *XBOX Gamepad* extension and object from the Local Multiplayer mod;
3. gives every keyboard event in Ultra a controller alternative (as an extra OR branch, so
   nothing fires twice);
4. adds the co-op battle logic around Ultra's own attack-menu events, and walkers for
   players 2 to 4 that copy player 1's movement and wall checks (`patcher/fwump/merge.py`);
5. writes the data back, recomputing the group jump offsets and the integrity checksum
   the Fusion runtime checks before it starts.

`patcher/selftest.py` checks the file-format code, and with `--game` it checks a built
`.dat`. A weekly workflow downloads the newest versions of both mods and checks that the
patcher still builds them.

## Credits

* **FNaF World**: Scott Cawthon
* **FNaF World Ultra**: Sprenglok31, Eliass_, Faxylordz and the Ultra team
* **FNaF World Local Multiplayer**: Mrexay, built on zekouillee's controller port
* **FNaF World Fixed** (the project Ultra is built on): plushcabinet
* **XBOX Gamepad extension**: Clickteam

This is an unofficial fan project, not affiliated with any of the above. All game content
belongs to its creators; this repository contains no game files.

## License

The patcher is licensed under the GNU AGPL v3 (see `LICENSE`). Its knowledge of the
Clickteam Fusion file format comes from the open-source
[CTFAK 2.0](https://github.com/CTFAK/CTFAK2.0) (AGPL-3.0) and
[Anaconda](https://github.com/fnmwolf/Anaconda) (GPL-3.0) projects.
