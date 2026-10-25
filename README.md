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
runs their own copy of the game; the host owns the save and operates mouse menus.
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

* **Controller support** (Xbox-style / XInput, up to 4 at once) everywhere Ultra has keyboard
  controls: walking around, the map, running from battles, dialogue, and the minigames.
  The mouse, touch and keyboard controls keep working as before.
* **Co-op battles.** Every attack turn belongs to a player. When it is your character's turn,
  pick the attack on *your* controller. The attack list highlights your choice and the line at
  the bottom shows whose turn it is (`P2: ...`). Release A before confirming a new turn.
* Turns are shared out over however many controllers are plugged in:
  * 1 controller: you play every turn
  * 2 controllers: P1 plays party slots 1 and 3, P2 plays slots 2 and 4
  * 3 controllers: P1 plays slots 1 and 4, P2 slot 2, P3 slot 3
  * 4 controllers: one slot each (like the Local Multiplayer mod)

  This applies to both rows of your party, the same way the Local Multiplayer mod did it.
  Controllers can join or leave mid-game; the turns rebalance automatically.
* **Everyone walks** (new in this merge). In the overworld, players 2 to 4 each get their
  own Freddy to walk around with, tinted so you can tell them apart: player 2 dark blue-grey,
  player 3 golden, player 4 red. Player 1's Freddy is the real one: it's the one that talks
  to characters, opens chests and runs into battles. The others walk at the same speed,
  can't pass walls or barriers, get pulled along when player 1 walks off, and wait out of
  sight during battles.
* **F9** (while exploring) makes the **keyboard/mouse player Player 1** and turns the
  controllers into Players 2 to 4. Press it again to switch back. A sparkle sound means
  keyboard = P1, a "tink" means controllers only. This is for a host who plays with mouse and
  keyboard while friends use local controllers. Native online mode assigns P1 automatically.

### Controls

| Controller | Does |
|---|---|
| Left stick / D-pad | walk (each player their own Freddy), move in minigames, move the attack highlight in battle |
| **A** | confirm, pick the highlighted attack, jump (minigames) |
| **B** (hold) | run away from a battle (same as holding **R**) |
| **X** | fire (minigames) |
| **Back / View** (hold) | show the map (same as holding **Tab**) |
| **RB** | switch party in battle |

Menus (main menu, party, chips, bytes, shops, options) are still mouse/touch. On Steam Deck,
tap the touchscreen or use the right trackpad as a mouse. In native online mode,
the host operates these menus for the shared game.

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
   and **E** to switch parties. Follow the `P#:` prompt for battle turns.
6. **F10 → Leave session** leaves the game. Guests return to their own title screen;
   the host's progress stays on the host's computer.

The shared Cloudflare relay is free and keeps lobby sockets connected while idle.
Free hosting has daily capacity limits and no guarantee of zero downtime. Service
configuration and hosting details are in [online/README.md](online/README.md).

For streaming an existing local session, Parsec or Sunshine/Moonlight can still
provide remote controllers; the native lobby mode uses a separate game copy on each computer.

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
