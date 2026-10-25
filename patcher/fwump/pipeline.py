"""One call that turns FNaF World Ultra + the Local Multiplayer exe into the merged game."""
import os
import shutil

from .evb import t_gv
from .merge import OVERWORLD, Merger, MergeError
from .online import add_online, compatibility_id, find_extension, write_settings

VERSION = "1.1.0"


def build(ultra_dir, mp_exe, out_dir, log=print, debug=False, test_jump=False, baseline=False,
          companions=True, online_extension=None, relay_url=None):
    if os.path.abspath(out_dir) == os.path.abspath(ultra_dir):
        raise MergeError("choose an output folder different from the FNaF World Ultra folder")
    log("reading FNaF World Ultra from %s" % ultra_dir)
    m = Merger(ultra_dir, mp_exe, log=log)
    m.setup_globals()
    m.add_gamepad()
    if not baseline:
        total = 0
        walk = (t_gv(m.G["walk_mask"]),)
        for f in m.frames:
            # in the overworld every player has their own walker, so player 1's
            # walker only listens to player 1's controller there
            total += m.mirror_keys(f, walk_mask_tokens=walk if f.name == OVERWORLD else None)
        log("controller support added to %d keyboard events" % total)
        m.battle_coop()
        if companions:
            m.companions()
    if debug:
        m.debug_dump()
    if test_jump:
        m.test_jump()
    online_extension = online_extension or find_extension()
    if online_extension and not baseline:
        add_online(m, online_extension)
        online_build_id = compatibility_id(m, online_extension)
    log("writing %s" % out_dir)
    m.write(out_dir)
    if online_extension and not baseline:
        shutil.copy2(online_extension, os.path.join(out_dir, "Modules", "FWUMOnline.mfx"))
        notice = os.path.join(os.path.dirname(online_extension), "FWUM-THIRD-PARTY-NOTICES.txt")
        if os.path.isfile(notice):
            shutil.copy2(notice, os.path.join(out_dir, "FWUM-THIRD-PARTY-NOTICES.txt"))
        write_settings(out_dir, relay_url, online_build_id)
    with open(os.path.join(out_dir, "MULTIPLAYER-README.txt"), "w", encoding="utf-8") as fh:
        fh.write(PLAY_NOTES)
    log("done")
    return out_dir


PLAY_NOTES = """FNaF World Ultra Multiplayer (patcher v%s)
==========================================

Start "Fnaf World Ultra.exe" in this folder (Steam Deck: add it to Steam as a
non-Steam game and force Proton in its Compatibility settings).

Controllers (Xbox-style, up to 4; Steam Deck controls count as controller 1):
  Left stick / D-pad   walk (everyone has a Freddy), move in minigames
  A                    confirm / jump (minigames) / pick the highlighted attack
  B (hold)             run away from a battle (same as holding R)
  X                    fire (minigames)
  Back / View (hold)   show the map (same as holding Tab)
  RB                   switch party in battle

Overworld: players 2-4 each walk their own tinted Freddy (P2 dark blue-grey,
P3 golden, P4 red). Player 1's Freddy is the one that talks, opens chests and
starts battles; the others stay within a screen of player 1.

Co-op battles: every attack turn belongs to one player. The player whose turn it
is picks the attack on their controller (D-pad/stick up and down, then A); the
bottom line shows "P2: ..." etc. With 2 controllers, P1 plays slots 1 and 3 and
P2 slots 2 and 4; with 3 or 4 controllers the turns are spread over everyone.
The mouse still works for any turn.

F9 (while exploring): the keyboard/mouse player becomes Player 1 and the
controllers become Players 2-4 (press again to switch back). Handy when the
host plays with mouse and keyboard and a friend joins over the internet.

Playing online: host with Parsec (Windows) or Sunshine + Moonlight (Steam Deck);
the friend's controller shows up as an extra controller. Setup steps are on the
project page.

Native online preview (builds with the online extension): click Online co-op or
press F10. Host game makes a visible lobby; leave Code empty for an open lobby,
or use exactly four digits. Friends select the lobby, enter its code if needed,
and choose Join selected. The host chooses Start co-op. Everyone runs their own
copy, and the host controls the save and mouse menus. Keyboard guests use
WASD/arrows, Z/Enter to confirm, R to flee, Tab for the map, and E to switch party.
Native mode assigns one player per computer and handles keyboard P1 automatically.
This preview needs a configured lobby service; see online/README.md in the project.
""" % VERSION
