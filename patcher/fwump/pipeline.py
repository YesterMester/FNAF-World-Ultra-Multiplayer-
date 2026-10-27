"""One call that turns FNaF World Ultra + the Local Multiplayer exe into the merged game."""
import os
import shutil

from .evb import t_gv
from .merge import OVERWORLD, Merger, MergeError
from .online import add_online, compatibility_id, find_extension, write_settings
from .launcher import write_launcher

VERSION = "1.2.0"


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
            total += m.mirror_keys(f, mask_tokens=walk if f in [m.frames[i] for i in (14, 23, 24, 25, 26)] else None,
                                   walk_mask_tokens=walk if f in [*m.frames[4:9], m.frames[20]] else None)
        log("controller support added to %d keyboard events" % total)
        m.battle_coop()
        if companions:
            m.companions()
        from .minigames import add_minigames
        add_minigames(m)
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
    write_launcher(out_dir)
    log("done")
    return out_dir


PLAY_NOTES = """FNaF World Ultra Multiplayer (patcher v%s)
==========================================

Windows: start "Fnaf World Ultra.exe" in this folder.
Steam Deck desktop: open "Play Multiplayer.sh". It finds your installed Proton
and Steam runtime automatically. For Gaming Mode, add the EXE to Steam as a
non-Steam game and force Proton in its Compatibility settings.

Controllers (Xbox-style, up to 4; Steam Deck controls count as controller 1):
  Left stick / D-pad   walk / menu focus / attack highlight
  A                    confirm / jump (minigames) / pick the highlighted attack
  B (hold)             run away from a battle (same as holding R)
  X                    fire (minigames)
  Back / View (hold)   show the map (same as holding Tab)
  RB                   swap only the acting character with its reserve
  Start                world toolbar / P1 starts a valid party
  Party editor         B: next owned slot; X: reset yours; Y: skin; LB/RB: category
  Options sliders      A: edit; Left/Right: adjust; A/B: done

Overworld: each player appears as their first assigned active character, with
optional unlocked cosmetics. Online cameras follow each player in the shared
area. NPC conversations show every current player's first character side by side.
Local co-op shares a camera. Travel, story and minigame outcomes are shared.

Co-op battles: every attack turn belongs to one player. The player whose turn it
is picks the attack on their controller (D-pad/stick up and down, then A); the
bottom line shows "P2: ..." etc. With 2 controllers, P1 plays slots 1 and 3 and
P2 slots 2 and 4; with 3 or 4 controllers the turns are spread over everyone.
Release A before confirming a new turn. Offline mouse assistance works for any
turn; online the host's mouse can choose attacks for P1's assigned slots.

F9 (while exploring): the keyboard/mouse player becomes Player 1 and the
controllers become Players 2-4 (press again to switch back). Handy when the
host plays with mouse and keyboard and friends use local controllers. Native
online sessions assign one player per computer automatically and ignore F9.

Playing online: click Online co-op or
press F10. Host game makes a visible lobby; leave Code empty for an open lobby,
or use exactly four digits. Friends select the lobby, enter its code if needed,
and choose Join selected. The host chooses Start co-op. Everyone runs their own
copy, and the host owns the shared simulation and save. D-pad/A/B operate menus. Keyboard guests use
WASD/arrows, Z/Enter to confirm, R to flee, Tab for the map, and E to swap only the acting slot with its reserve.
Native mode assigns one player per computer. The party editor allows duplicate
picks and independent online roster browsing; edit only your outlined P# slots.
Fishing, clock rooms, Foxy Fighters, FNaF 57, Foxy.exe and Rainbow accept co-op
participants. Mediocore Night shares its office/cameras/tasks; B leaves the round.
Skins are cosmetic and stored separately in FWUM-skins.ini.
The public lobby service is included in the official patchers. Hosting and
joining are free and need no router setup or player account.
""" % VERSION
