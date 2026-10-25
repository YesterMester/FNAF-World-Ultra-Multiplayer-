"""One call that turns FNaF World Ultra + the Local Multiplayer exe into the merged game."""
import os

from .evb import t_gv
from .merge import OVERWORLD, Merger, MergeError

VERSION = "1.0.0"


def build(ultra_dir, mp_exe, out_dir, log=print, debug=False, test_jump=False, baseline=False,
          companions=True):
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
    log("writing %s" % out_dir)
    m.write(out_dir)
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
""" % VERSION
