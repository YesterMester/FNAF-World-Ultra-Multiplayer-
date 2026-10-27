"""Builds FNaF World Ultra Multiplayer: FNaF World Ultra + controller co-op
from the FNaF World Local Multiplayer mod.

What gets added to Ultra:
  * the XBOX Gamepad extension (taken from the Local Multiplayer mod)
  * gamepad control everywhere Ultra has keyboard control (walking, map,
    running from battle, dialogue, minigames), for any connected controller
  * co-op battles: each attack turn belongs to one player; the controller
    of that player picks the attack (D-pad/stick to choose, A to confirm),
    with turns shared out between however many controllers are connected
  * players 2-4 walk their own Freddy in the overworld
"""
import os
import shutil
import struct
import zlib

from . import fusion
from .ccn import Game, Reader
from .evb import (F_MAX, F_MIN, F_TOSTRING, Ids, act, a_add_gv, a_set_gv, clone, cond, c_gv, expr, group,
                  p_cmp, p_expr, t_altval, t_close, t_ext, t_func, t_gv, t_long, t_objcount,
                  t_op, t_comma)
from .fusion import (Instance, NewChunk, ObjectDef, Param, build_object_chunks, parse_frames,
                     parse_objects, write_game)

ULTRA_DAT = "Fnaf World Ultra.dat"
OVERWORLD = "5: Overworld"

# XBOX Gamepad extension: condition index -> meaning. Buttons take a mask of players
# (1, 2, 4, 8); "connected" takes a single pad number 0-3.
PAD_CONNECTED, PAD_A, PAD_B, PAD_X, PAD_Y, PAD_BACK = 0, 1, 2, 3, 4, 5
PAD_LB, PAD_RB, PAD_START = 7, 9, 11
PAD_UP, PAD_DOWN, PAD_LEFT, PAD_RIGHT = 12, 13, 14, 15
EXP_LH, EXP_LV = 0, 1
ANY_PAD = 15
STICK = 50  # stick threshold (the extension reports -100..100; vertical is positive downwards)

# keyboard key -> gamepad alternatives. ('pad', cond) is a button, ('stick', exp, op, value)
# a left-stick direction.
KEYMAP = {
    87: [("pad", PAD_UP), ("stick", EXP_LV, "<", -STICK)],     # W
    38: [("pad", PAD_UP), ("stick", EXP_LV, "<", -STICK)],     # Up
    83: [("pad", PAD_DOWN), ("stick", EXP_LV, ">", STICK)],    # S
    40: [("pad", PAD_DOWN), ("stick", EXP_LV, ">", STICK)],    # Down
    65: [("pad", PAD_LEFT), ("stick", EXP_LH, "<", -STICK)],   # A
    37: [("pad", PAD_LEFT), ("stick", EXP_LH, "<", -STICK)],   # Left
    68: [("pad", PAD_RIGHT), ("stick", EXP_LH, ">", STICK)],   # D
    39: [("pad", PAD_RIGHT), ("stick", EXP_LH, ">", STICK)],   # Right
    9: [("pad", PAD_BACK)],                                     # Tab: map
    82: [("pad", PAD_B)],                                       # R: run from battle
    13: [("pad", PAD_A)],                                       # Enter
    90: [("pad", PAD_A)],                                       # Z: jump (minigames)
    88: [("pad", PAD_X)],                                       # X: fire (minigames)
    16: [("pad", PAD_X)],                                       # Shift: fire (minigames)
}

KEY_F9 = 120


class MergeError(Exception):
    pass


class Merger:
    def __init__(self, ultra_dir, mp_exe, log=print):
        self.log = log
        self.ultra_dir = ultra_dir
        dat = os.path.join(ultra_dir, ULTRA_DAT)
        if not os.path.exists(dat):
            raise MergeError("%s not found in %s" % (ULTRA_DAT, ultra_dir))
        self.ultra = Game(dat)
        self.mp = Game(mp_exe)
        if self.ultra.name != "FNaF World Ultra":
            raise MergeError("unexpected game in %s: %r" % (dat, self.ultra.name))
        fusion.CRYPT["game"] = self.ultra
        self.objs = parse_objects(self.ultra)
        self.frames = parse_frames(self.ultra)
        self.mp_objs = parse_objects(self.mp)
        self.dirty = set()
        self.globals_chunk = self.ultra.chunk(0x2232).decode(self.ultra)
        self.new_globals = []
        self.line = 30000

    # ------------------------------------------------------------------ helpers
    def frame(self, name):
        for f in self.frames:
            if f.name == name:
                return f
        raise MergeError("frame %r not found" % name)

    def oi(self, name, frame=None):
        """Object handle by name; when a frame is given, prefer objects placed in it."""
        cands = [o.index for o in self.objs if o.name == name]
        if frame is not None:
            placed = set(i.object_info for i in frame.instances)
            inframe = [c for c in cands if c in placed]
            if inframe:
                cands = inframe
        if not cands:
            raise MergeError("object %r not found" % name)
        return cands[0]

    def otype(self, oi):
        return self.objs[oi].type

    def alloc_global(self, name):
        count = struct.unpack_from("<h", self.globals_chunk, 0)[0]
        idx = count + len(self.new_globals)
        self.new_globals.append(name)
        return idx

    def build_globals(self):
        d = self.globals_chunk
        count = struct.unpack_from("<h", d, 0)[0]
        values = d[2:2 + 4 * count]
        types = d[2 + 4 * count:2 + 5 * count]
        tail = d[2 + 5 * count:]
        n = count + len(self.new_globals)
        return struct.pack("<h", n) + values + b"\0\0\0\0" * len(self.new_globals) + \
            types + b"\0" * len(self.new_globals) + tail

    def blocks(self, f):
        return [b for t, b in f.events.sections if t == b"ERev"]

    def sync_groups(self, f):
        f.events.groups = [g for b in self.blocks(f) for g in b]
        self.dirty.add(id(f))

    def next_line(self):
        self.line += 1
        return self.line

    def ensure_instance(self, f, oi):
        if any(i.object_info == oi for i in f.instances):
            return
        it = Instance()
        it.handle = max((i.handle for i in f.instances), default=-1) + 1
        it.object_info = oi
        it.x = -400
        it.y = -400
        it.parent_type = 0
        it.parent_handle = 0
        it.layer = 0
        it.instance = 0
        f.instances.append(it)
        if self.objs[oi].type >= 2:
            f.events.max_object_info += 1
        self.dirty.add(id(f))

    def setup_globals(self):
        """Global values used by the added logic (appended after Ultra's own)."""
        names = ["pads", "players", "turn_slot", "turn_owner", "turn_mask", "selected", "confirmed",
                 "keyboard_p1", "walk_mask", "confirm_ready", "previous_mask"]
        for k in (2, 3, 4):
            names += ["p%d_mask" % k, "p%d_active" % k, "p%d_moving" % k]
        names += ["online_session"]
        self.G = {n: self.alloc_global("mp_" + n) for n in names}

    # ------------------------------------------------------------- extension
    def add_gamepad(self):
        d = self.ultra.chunk(0x2234).decode(self.ultra)
        r = Reader(d)
        count = r.u16()
        slots = r.u16()
        for _ in range(count):
            st = r.pos
            size = abs(r.i16())
            r.pos = st + 16
            if r.wstr().lower() == "xboxgamepad.mfx":
                raise MergeError("this FNaF World Ultra already contains the XBOX Gamepad extension; "
                                 "it was probably patched already - use an unmodified copy")
            r.pos = st + size
        md = self.mp.chunk(0x2234).decode(self.mp)
        mr = Reader(md)
        mcount = mr.u16()
        mr.u16()
        entry = None
        for _ in range(mcount):
            st = mr.pos
            size = abs(mr.i16())
            mr.pos = st + 16
            if mr.wstr() == "XBOXGamepad.mfx":
                entry = bytearray(md[st:st + size])
            mr.pos = st + size
        if entry is None:
            raise MergeError("XBOXGamepad extension not found in the Local Multiplayer exe")
        self.xhandle = slots
        struct.pack_into("<h", entry, 2, self.xhandle)
        self.ext_chunk = struct.pack("<HH", count + 1, slots + 1) + d[4:] + bytes(entry)
        self.xtype = 32 + self.xhandle

        src = [o for o in self.mp_objs if o.name == "XBOX Gamepad"]
        if not src:
            raise MergeError("XBOX Gamepad object not found in the Local Multiplayer exe")
        src = src[0]
        o = ObjectDef(len(self.objs))
        o.header = struct.pack("<hh", o.index, self.xtype) + src.header[4:]
        o.name = "MP Gamepad"
        o.shader = b"\0\0\0\0"
        o.props = src.props
        self.objs.append(o)
        self.xoi = o.index
        mfx = next((p for p in self.mp.packfiles if p.name == "XBOXGamepad.mfx"), None)
        if mfx is None:
            raise MergeError("XBOXGamepad.mfx not packed in the Local Multiplayer exe")
        data = mfx.data
        self.mfx_bytes = zlib.decompress(data) if data[:2] == b"\x78\xda" else data

    # --------------------------------------------------------- pad conditions
    def pad_cond(self, ids, index, mask_tokens, negate=False):
        return cond(ids, self.xtype, -81 - index, self.xoi, [p_expr(*mask_tokens)],
                    flags=32, other=1 if negate else 0)

    def stick_cond(self, ids, exp, op, value, mask_tokens, negate=False):
        if negate:
            op = {">": "<=", "<": ">=", ">=": "<", "<=": ">"}[op]
        left = Param(22, expr(t_ext(self.xtype, exp, self.xoi), *mask_tokens, t_close()))
        return cond(ids, -1, -3, params=[left, p_cmp(op, t_long(value))])

    def alt_conds(self, ids, alt, mask_tokens, negate=False):
        if alt[0] == "pad":
            return [self.pad_cond(ids, alt[1], mask_tokens, negate)]
        return [self.stick_cond(ids, alt[1], alt[2], alt[3], mask_tokens, negate)]

    # ---------------------------------------------------- keyboard mirroring
    @staticmethod
    def key_of(c):
        if c.object_type == -6 and c.num in (-1, -2) and c.params and c.params[0].code == 14:
            return struct.unpack_from("<H", c.params[0].data, 0)[0]
        return None

    @staticmethod
    def branches(g):
        """Split condition indices into OR branches; returns (list of index lists, or-num)."""
        out = [[]]
        ornum = None
        for i, c in enumerate(g.conditions):
            if c.object_type == -1 and c.num in (-24, -25):
                ornum = c.num
                out.append([])
            else:
                out[-1].append(i)
        return out, ornum

    WALK_KEYS = (87, 38, 83, 40, 65, 37, 68, 39)

    def mirror_keys(self, f, mask_tokens=None, walk_mask_tokens=None):
        """Give every keyboard condition of the frame a gamepad equivalent.
        Walking keys can listen to their own controller mask (the player-1 walker)."""
        any_pad = mask_tokens or (t_long(ANY_PAD),)
        walk_pad = walk_mask_tokens or any_pad
        mask_for = lambda key: walk_pad if key in self.WALK_KEYS else any_pad
        ids = Ids(f)
        changed = 0
        for blk in self.blocks(f):
            for g in blk:
                keys = [(i, self.key_of(c)) for i, c in enumerate(g.conditions)]
                keys = [(i, k) for i, k in keys if k in KEYMAP]
                if not keys:
                    continue
                branches, ornum = self.branches(g)
                new_conds = []
                extra_branches = []
                for br in branches:
                    bkeys = [(i, k) for i, k in keys if i in br]
                    pos_keys = [(i, k) for i, k in bkeys if not g.conditions[i].other_flags & 1]
                    conds = []
                    for i in br:
                        c = g.conditions[i]
                        conds.append(c)
                        k = self.key_of(c)
                        if k in KEYMAP and c.other_flags & 1:
                            # "key not held": also require the pad to be idle
                            for alt in KEYMAP[k]:
                                conds.extend(self.alt_conds(ids, alt, mask_for(k), negate=True))
                    new_conds.append(conds)
                    if len(pos_keys) == 1:
                        ki, k = pos_keys[0]
                        pressed = g.conditions[ki].num == -1
                        for alt in KEYMAP[k]:
                            nb = []
                            for i in br:
                                c = g.conditions[i]
                                if i == ki:
                                    nb.extend(self.alt_conds(ids, alt, mask_for(k)))
                                    if pressed:
                                        nb.append(cond(ids, -1, -7))
                                else:
                                    cc = clone(c)
                                    if cc.identifier:
                                        cc.identifier = ids.take()
                                    nb.append(cc)
                                    kk = self.key_of(c)
                                    if kk in KEYMAP and c.other_flags & 1:
                                        for a2 in KEYMAP[kk]:
                                            nb.extend(self.alt_conds(ids, a2, mask_for(kk), negate=True))
                            extra_branches.append(nb)
                    elif len(pos_keys) > 1:
                        # combinations of held keys (diagonals): map each key to its
                        # D-pad button only
                        nb = []
                        for i in br:
                            c = g.conditions[i]
                            k = self.key_of(c)
                            if k in KEYMAP and not c.other_flags & 1:
                                nb.append(self.pad_cond(ids, KEYMAP[k][0][1], mask_for(k)))
                            else:
                                cc = clone(c)
                                if cc.identifier:
                                    cc.identifier = ids.take()
                                nb.append(cc)
                                if k in KEYMAP and c.other_flags & 1:
                                    for a2 in KEYMAP[k]:
                                        nb.extend(self.alt_conds(ids, a2, mask_for(k), negate=True))
                        extra_branches.append(nb)
                ornum = ornum or -25
                out = []
                for bi, conds in enumerate(new_conds + extra_branches):
                    if bi:
                        out.append(cond(ids, -1, ornum, flags=0))
                    out.extend(conds)
                if len(out) > 255:
                    raise MergeError("event too large after mirroring")
                g.conditions = out
                changed += 1
        if changed:
            self.ensure_instance(f, self.xoi)
            self.sync_groups(f)
        return changed

    # ------------------------------------------------------------- battle co-op
    def battle_coop(self):
        f = self.frame(OVERWORLD)
        ids = Ids(f)
        X = lambda name: self.oi(name, f)
        b0 = self.blocks(f)[0]

        G = self.G
        G_NP, G_NPL, G_SLOT, G_OWN = G["pads"], G["players"], G["turn_slot"], G["turn_owner"]
        G_MASK, G_SEL, G_CONF, G_KB = G["turn_mask"], G["selected"], G["confirmed"], G["keyboard_p1"]
        G_READY, G_PREV = G["confirm_ready"], G["previous_mask"]
        mask = (t_gv(G_MASK),)
        def owner_actions():
            # Keep Ultra's selected character intact: starting a nested fastloop
            # here resets the caller's object selection in the compiled runtime.
            return [
                a_set_gv(G_OWN, t_func(F_MAX), t_gv(G_SLOT), t_comma(), t_long(1), t_close(),
                         t_op("-"), t_long(1)),
                a_set_gv(G_OWN, t_gv(G_OWN), t_op("mod"), t_gv(G_NPL)),
                # With keyboard P1, controller bits start at player 2. The two
                # Min gates make the keyboard's turn (or no controller) mask 0.
                a_set_gv(G_MASK, t_long(2), t_op("^"), t_func(F_MAX), t_gv(G_OWN), t_op("-"),
                         t_gv(G_KB), t_comma(), t_long(0), t_close(),
                         t_op("*"), t_func(F_MIN), t_long(1), t_comma(), t_gv(G_NP), t_close(),
                         t_op("*"), t_func(F_MIN), t_long(1), t_comma(), t_gv(G_OWN), t_op("+"),
                         t_long(1), t_op("-"), t_gv(G_KB), t_close()),
            ]
        self.turn_owner_actions = owner_actions

        movb = X("mov button")
        plr = X("plr character")
        T = lambda oi: self.otype(oi)
        IDX = 20  # alterable value of "mov button" holding its position in the list

        # --- 1. turn start: remember whose turn it is
        k = self.find(b0, lambda g: any(a.object_type == -1 and a.num == 14 and
                                        b"c\0r\0e\0a\0t\0e\0 \0b\0u\0t\0t\0o\0n" in a.params[0].data
                                        for a in g.actions))
        start = b0[k]
        start.actions[0:0] = [a_set_gv(G_SLOT, t_altval(T(plr), plr, 0)),
                              a_set_gv(G_SEL, t_long(0)), a_set_gv(G_READY, t_long(0))] + owner_actions()

        # --- 2. remember each attack button's position in the list
        k = self.find(b0, lambda g: any(c.object_type == -1 and c.num == -16 and
                                        b"c\0r\0e\0a\0t\0e\0 \0b\0u\0t\0t\0o\0n" in c.params[0].data
                                        for c in g.conditions))
        create = b0[k]
        loopidx = Param(22, expr(struct.pack("<hhH", -1, 46, 6), self._t_str("create button"), t_close()))
        create.actions.append(act(T(movb), 31, movb, [Param(50, struct.pack("<hi", IDX, 0)), loopidx]))

        # --- 3. per-frame bookkeeping at the very top of the frame
        top = []
        top.append(group([cond(ids, -1, -1)], [a_set_gv(G_NP, t_long(0)), a_set_gv(G_MASK, t_long(0)),
                                                a_set_gv(G_CONF, t_long(0))], line=self.next_line()))
        for pad in range(4):  # "connected" takes a pad number 0-3, not a mask
            top.append(group([self.pad_cond(ids, PAD_CONNECTED, (t_long(pad),))],
                             [a_add_gv(G_NP, t_long(1))], line=self.next_line()))
        top.append(group([cond(ids, -1, -1)], [a_set_gv(G_NPL, t_gv(G_NP), t_op("+"), t_gv(G_KB))],
                         line=self.next_line()))
        top.append(group([c_gv(ids, G_NPL, "=", t_long(0))], [a_set_gv(G_NPL, t_long(1))],
                         line=self.next_line()))
        # Assign at frame start and synchronously at the turn-opening action.
        # A mask calculated only at frame start belongs to the previous turn
        # for one frame, allowing held input from the wrong player to confirm.
        top.append(group([cond(ids, -1, -1)], owner_actions(), line=self.next_line()))
        top.append(group([c_gv(ids, G_PREV, "<>", t_gv(G_MASK))],
                         [a_set_gv(G_READY, t_long(0)), a_set_gv(G_PREV, t_gv(G_MASK))], line=self.next_line()))
        # F9: keyboard/mouse becomes player 1 (or back); a sound tells which way
        f9 = struct.pack("<HH", KEY_F9, 0)
        on_snd = self.find_sound_action(f, "PREL_LOGO_SPARKLE_PO0")
        off_snd = self.find_sound_action(f, "tink")
        top.append(group([cond(ids, -6, -1, params=[Param(14, f9)]),
                          c_gv(ids, G_KB, "=", t_long(0))],
                         [a_set_gv(G_KB, t_long(2))] + ([on_snd] if on_snd else []),
                         line=self.next_line()))
        top.append(group([cond(ids, -6, -1, params=[Param(14, f9)]),
                          c_gv(ids, G_KB, "=", t_long(1))],
                         [a_set_gv(G_KB, t_long(0))] + ([off_snd] if off_snd else []),
                         line=self.next_line()))
        top.append(group([c_gv(ids, G_KB, "=", t_long(2))], [a_set_gv(G_KB, t_long(1))],
                         line=self.next_line()))
        # the main walker follows controller 1, or only the keyboard when keyboard is P1
        top.append(group([c_gv(ids, G_KB, "=", t_long(0))], [a_set_gv(G["walk_mask"], t_long(1))],
                         line=self.next_line()))
        top.append(group([c_gv(ids, G_KB, "=", t_long(1))], [a_set_gv(G["walk_mask"], t_long(0))],
                         line=self.next_line()))
        b0[0:0] = top
        self.top_count = len(top)

        # --- 4. choosing and confirming attacks with the turn owner's controller
        k = self.find(b0, lambda g: g.conditions and g.conditions[0].object_type >= 32 and
                      g.conditions[0].num == -87 and self._objparam(g.conditions[0]) == movb)
        touch = b0[k]
        grp_flags, rc = touch.flags, touch.restrict_cpt
        count_gt0 = lambda: cond(ids, T(movb), -32, movb, [p_cmp(">", t_long(0))])
        # A button held before a turn opens must be released before confirming
        # that turn. This also protects reassignment after a player leaves.
        nav = [group([count_gt0(), self.pad_cond(ids, PAD_A, mask, negate=True)],
                     [a_set_gv(G_READY, t_long(1))], flags=grp_flags, line=self.next_line(), restrict_cpt=rc)]
        for padc, exp, op, delta in ((PAD_UP, EXP_LV, "<", -1), (PAD_DOWN, EXP_LV, ">", 1)):
            for alt in (("pad", padc), ("stick", exp, op, STICK if op == ">" else -STICK)):
                conds = self.alt_conds(ids, alt, mask) + [cond(ids, -1, -7), count_gt0()]
                if delta < 0:
                    conds.append(c_gv(ids, G_SEL, ">", t_long(0)))
                else:
                    conds.append(c_compare(ids, (t_gv(G_SEL), t_op("+"), t_long(1)), "<",
                                           (t_objcount(T(movb), movb),)))
                nav.append(group(conds, [a_add_gv(G_SEL, t_long(delta))], flags=grp_flags,
                                 line=self.next_line(), restrict_cpt=rc))
        # highlight: other buttons fade (alpha 0 = opaque in Fusion), the chosen one shows
        # its description like a mouse hover would
        desc = X("hud move description")
        alpha = lambda v: act(T(movb), 65, movb, [p_expr(t_long(v))])
        hl = []
        hl.append(group([count_gt0(), c_gv(ids, G_MASK, ">", t_long(0))], [alpha(140)],
                        flags=grp_flags, line=self.next_line(), restrict_cpt=rc))
        hl.append(group([c_gv(ids, G_MASK, ">", t_long(0)),
                         cond(ids, T(movb), -27, movb, [Param(50, struct.pack("<hi", IDX, 0)),
                                                         p_cmp("=", t_gv(G_SEL))], other=32)],
                        [alpha(0)],
                        flags=grp_flags, line=self.next_line(), restrict_cpt=rc))
        # description: must run after Ultra's "mouse not over a button -> hide description"
        hide = self.find(b0, lambda g: any(c.object_type == -6 and c.num == -4 and c.other_flags & 1
                                           and self._objparam(c) == movb for c in g.conditions))
        hg = b0[hide]
        # Ultra's own hover action picks the paragraph (its numbering differs from
        # the GetParagraph expression's), then the player tag goes in front
        show_desc = next((a for g in b0 if any(c.object_type == -6 and c.num == -4 and not c.other_flags & 1
                                               and self._objparam(c) == movb for c in g.conditions)
                          for a in g.actions if a.object_info == desc and a.num == self.SETPARAGRAPH), None)
        if show_desc is None:
            raise MergeError("attack description event not found")
        b0.insert(hide + 1, group(
            [c_gv(ids, G_MASK, ">", t_long(0)),
             cond(ids, T(movb), -27, movb, [Param(50, struct.pack("<hi", IDX, 0)),
                                             p_cmp("=", t_gv(G_SEL))], other=32)],
            [clone(show_desc),
             act(T(desc), self.SETSTRING, desc,
                 [p_expr(self._t_str("P"), t_op("+"), t_func(F_TOSTRING), t_gv(G_OWN), t_op("+"), t_long(1),
                         t_close(), t_op("+"), self._t_str(": "), t_op("+"),
                         struct.pack("<hhHHh", T(desc), 81, 10, desc, 0))]),
             act(T(desc), 27, desc)],
            flags=hg.flags, line=self.next_line(), restrict_cpt=hg.restrict_cpt))
        # confirm with A: same as clicking the highlighted button
        confirm_conds = [self.pad_cond(ids, PAD_A, mask), c_gv(ids, G_READY, "=", t_long(1)), cond(ids, -1, -7),
                         cond(ids, T(movb), -27, movb, [Param(50, struct.pack("<hi", IDX, 0)),
                                                         p_cmp("=", t_gv(G_SEL))], other=32)]
        for c in touch.conditions[1:]:
            cc = clone(c)
            if cc.identifier:
                cc.identifier = ids.take()
            confirm_conds.append(cc)
        confirm = group(confirm_conds, [clone(a) for a in touch.actions] + [a_set_gv(G_CONF, t_long(1))],
                        flags=grp_flags, line=self.next_line(), restrict_cpt=rc)
        k = b0.index(touch)
        b0[k + 1:k + 1] = nav + hl + [confirm]

        # --- 5. other events that react to clicking an attack button
        for blk in self.blocks(f):
            i = 0
            while i < len(blk):
                g = blk[i]
                hit = [j for j, c in enumerate(g.conditions) if c.object_type >= 32 and c.num == -87
                       and self._objparam(c) == movb]
                if hit and g is not touch:
                    ng = clone(g)
                    j = hit[0]
                    ng.conditions[j] = c_gv(ids, G_CONF, "=", t_long(1))
                    for c in ng.conditions:
                        if c.identifier and c is not ng.conditions[j]:
                            c.identifier = ids.take()
                    ng.line = self.next_line()
                    blk.insert(i + 1, ng)
                    i += 1
                i += 1

        # --- 6. switch party with RB (controller 1), as if its button was clicked
        swp = X("hud switch party")
        for blk in self.blocks(f):
            for g in blk:
                if g.conditions and g.conditions[0].object_type >= 32 and g.conditions[0].num == -87 \
                        and self._objparam(g.conditions[0]) == swp and len(g.actions) > 10:
                    self.add_or_branch(ids, g, 0, [self.pad_cond(ids, PAD_RB, (t_long(ANY_PAD),)),
                                                   cond(ids, -1, -7)])
        self.ensure_instance(f, self.xoi)
        self.sync_groups(f)
        self.log("battle co-op: added to %r" % f.name)

    # ---------------------------------------------------------- companions
    TINTS = {2: (110, 160, 255), 3: (255, 235, 90), 4: (255, 120, 120)}

    def companions(self):
        """Use Ultra's movement and collision in the overworld and underground."""
        for f in [*self.frames[4:9], self.frames[20]]:
            self._companions(f)

    def _companions(self, f):
        ids = Ids(f)
        G = self.G
        hit = self.oi("plr hitbox", f)
        flight = f is self.frames[23]
        spr = self.oi("plr overworld" if f is self.frames[4] else "spr plane foxy" if flight else
                      "spr player" if f is self.frames[20] else "plr sprite", f)
        joy = self.oi("obj joy body", f)
        T = self.otype
        layer_of = next(i.layer for i in f.instances if i.object_info == hit)

        # templates from Ultra's own walker events
        tmpl_setpos = None
        for g in f.events.groups:
            for a in g.actions:
                if a.object_info == spr and a.num == 1 and a.params and a.params[0].code == 16 and \
                        struct.unpack_from("<H", a.params[0].data, 0)[0] == hit:
                    tmpl_setpos = a
                    break
            if tmpl_setpos:
                break
        if tmpl_setpos is None:
            # Some underground frames set X/Y independently. The same relative
            # position parameter from the overworld is valid in those frames.
            tmpl_setpos = next((clone(a) for g in self.frames[4].events.groups for a in g.actions
                                if a.object_info == self.oi("plr overworld", self.frames[4]) and
                                a.num == 1 and a.params and a.params[0].code == 16 and
                                struct.unpack_from("<H", a.params[0].data)[0] == hit), None)
        if tmpl_setpos is None:
            raise MergeError("walker follow event not found in %r" % f.name)
        # the group of solid objects (barriers, locks) Ultra's walker can't pass
        solid = next((c.params[0].data for g in f.events.groups for c in g.conditions
                      if c.object_info == hit and c.num == -4 and len(c.params) == 3 and
                      c.params[0].code == 1), None)

        def setpos(oi, parent):
            a = clone(tmpl_setpos)
            a.object_info = oi
            a.object_type = T(oi)
            d = bytearray(a.params[0].data)
            struct.pack_into("<H", d, 0, parent)
            a.params[0] = Param(16, bytes(d))
            return a

        def clone_obj(src, name, tint=None):
            o = ObjectDef(len(self.objs))
            so = self.objs[src]
            hdr = bytearray(so.header)
            struct.pack_into("<h", hdr, 0, o.index)
            if tint:
                # RGB coefficient (stored blue, green, red, alpha); drawn only with
                # the RGBA-filter ink flag set
                struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x1000)
                hdr[12:16] = bytes(tint[::-1]) + b"\xff"
            o.header = bytes(hdr)
            o.name = name
            o.shader = b"\0\0\0\0"
            props = bytearray(so.props)
            # leave every qualifier group: Ultra's events on e.g. the player's group
            # (warps, encounters) must not see the companions
            props[20:36] = struct.pack("<8h", *([-1] * 8))
            o.props = bytes(props)
            self.objs.append(o)
            self.ensure_instance(f, o.index)
            next(i for i in f.instances if i.object_info == o.index).layer = layer_of
            return o.index

        x = lambda oi: struct.pack("<hhHHh", T(oi), 11, 10, oi, 0)
        y = lambda oi: struct.pack("<hhHHh", T(oi), 1, 10, oi, 0)
        layer = lambda oi: struct.pack("<hhHHh", T(oi), 23, 10, oi, 0)
        speed = t_altval(T(joy), joy, 0)
        look = t_altval(T(joy), joy, 2)
        flag_off = lambda oi, n: cond(ids, T(oi), -24, oi, [p_expr(t_long(n))], other=32)

        def free_at(oi, xt, yt):
            """Conditions: nothing solid at (xt, yt) for object oi."""
            cs = [cond(ids, T(oi), -23, oi, [p_expr(*xt), p_expr(*yt)], other=1)]
            if solid is not None:
                cs.append(cond(ids, T(oi), -4, oi, [Param(1, solid), p_expr(*xt), p_expr(*yt)], other=1))
            return cs

        set_alt = lambda oi, idx, v: act(T(oi), 31, oi, [Param(50, struct.pack("<hi", idx, 0)),
                                                          p_expr(t_long(v))])
        alt_is = lambda oi, idx, v: c_compare(ids, (t_altval(T(oi), oi, idx),), "=", (t_long(v),))
        DX, DY = 10, 11  # spare alterable values of a companion's hitbox: wanted step
        events = []
        add = lambda conds, acts: events.append(group(conds, acts, line=self.next_line()))
        dirs = ((PAD_UP, ("stick", EXP_LV, "<", -STICK), DY, -1),
                (PAD_DOWN, ("stick", EXP_LV, ">", STICK), DY, 1),
                (PAD_LEFT, ("stick", EXP_LH, "<", -STICK), DX, -1),
                (PAD_RIGHT, ("stick", EXP_LH, ">", STICK), DX, 1))
        # Fusion direction (0 = right, 8 = up) of each step
        heading = {(1, 0): 0, (1, -1): 4, (0, -1): 8, (-1, -1): 12,
                   (-1, 0): 16, (-1, 1): 20, (0, 1): 24, (1, 1): 28}
        for k in (2, 3, 4):
            hk = clone_obj(hit, "mp hitbox %d" % k)
            sk = clone_obj(spr, "mp walker %d" % k, self.TINTS[k])
            ACT, MOV, MK = G["p%d_active" % k], G["p%d_moving" % k], G["p%d_mask" % k]
            mk = (t_gv(MK),)
            if f is self.frames[20] or flight:
                add([cond(ids, -3, -1, flags=0)], [act(T(hk), 17, hk, [p_expr(t_long(13 if flight else 12))])])
            # who controls this walker, and is it in play?
            add([cond(ids, -1, -1)], [a_set_gv(ACT, t_long(0)), a_set_gv(MOV, t_long(0))])
            add([c_gv(ids, G["keyboard_p1"], "=", t_long(0))], [a_set_gv(MK, t_long(1 << (k - 1)))])
            add([c_gv(ids, G["keyboard_p1"], "=", t_long(1))], [a_set_gv(MK, t_long(1 << (k - 2)))])
            add([c_compare(ids, (t_gv(G["pads"]), t_op("+"), t_gv(G["keyboard_p1"])), ">=", (t_long(k),))] +
                ([] if flight else [flag_off(hit, 1)]),
                [a_set_gv(ACT, t_long(1))])
            # not in play: wait (hidden) on top of player 1
            add([c_gv(ids, ACT, "=", t_long(0))], [act(T(sk), 26, sk), act(T(hk), 4, hk),
                 setpos(hk, hit), act(T(hk), 36, hk, [p_expr(t_long(31))])])
            # Sessions can start on the title/party screen. Such companions
            # haven't had an inactive overworld tick to receive a spawn point.
            add([c_gv(ids, ACT, "=", t_long(1)), flag_off(hk, 31)],
                [setpos(hk, hit), act(T(hk), 35, hk, [p_expr(t_long(31))])])
            add([c_gv(ids, ACT, "=", t_long(1))], [act(T(sk), 27, sk), set_alt(hk, DX, 0), set_alt(hk, DY, 0)])
            # which way this player wants to go, if it is free (the same test as
            # Ultra's own walker: a few pixels ahead, scenery and solid objects)
            for padc, stick, axis, sign in dirs:
                op = "+" if sign > 0 else "-"
                if axis == DX:
                    probe = ((x(hk), t_op(op), look), (y(hk),))
                else:
                    probe = ((x(hk),), (y(hk), t_op(op), look))
                for alt in (("pad", padc), stick):
                    add([c_gv(ids, ACT, "=", t_long(1))] + self.alt_conds(ids, alt, mk) + free_at(hk, *probe),
                        [set_alt(hk, axis, sign)])
            # walk with player 1's built-in movement and speed, so everyone walks alike
            for (dx, dy), d in heading.items():
                add([c_gv(ids, ACT, "=", t_long(1)), alt_is(hk, DX, dx), alt_is(hk, DY, dy)],
                    [act(T(hk), 6, hk, [Param(15, expr(speed))]), act(T(hk), 23, hk, [p_expr(t_long(d))]),
                     act(T(sk), 23, sk, [p_expr(t_long(d))]), act(T(hk), 5, hk), a_set_gv(MOV, t_long(1))])
            # stay within a screen of player 1; never get stuck inside scenery
            for axis, lim in (() if flight else ((11, 360), (1, 200))):
                src = x if axis == 11 else y
                setter = 2 if axis == 11 else 3
                for op, cmpop in (("+", ">"), ("-", "<")):
                    add([c_gv(ids, ACT, "=", t_long(1)), c_gv(ids, G["online_session"], "=", t_long(0)),
                         c_compare(ids, (src(hk),), cmpop, (src(hit), t_op(op), t_long(lim)))],
                        [act(T(hk), setter, hk, [p_expr(src(hit), t_op(op), t_long(lim))])])
            stuck = [[cond(ids, T(hk), -23, hk, [p_expr(x(hk)), p_expr(y(hk))])]]
            if solid is not None:
                stuck.append([cond(ids, T(hk), -4, hk, [Param(1, solid), p_expr(x(hk)), p_expr(y(hk))])])
            for c in stuck:
                add([c_gv(ids, ACT, "=", t_long(1))] + c, [setpos(hk, hit)])
            # the visible Freddy follows its hitbox and player 1's layer
            add([c_gv(ids, ACT, "=", t_long(1))],
                [setpos(sk, hk), act(T(sk), 61, sk, [p_expr(layer(hit))]),
                 act(T(hk), 61, hk, [p_expr(layer(hit))])])
            add([c_gv(ids, ACT, "=", t_long(1)), c_gv(ids, MOV, "=", t_long(1))],
                [act(T(sk), 17, sk, [Param(10, struct.pack("<h", 0 if flight else 1))])])
            add([c_gv(ids, ACT, "=", t_long(1)), c_gv(ids, MOV, "=", t_long(0))],
                [act(T(hk), 4, hk), act(T(sk), 17, sk, [Param(10, struct.pack("<h", 0))])])
        # A frame-specific offset from the battle frame can fall inside another
        # frame's child tree. Run after Ultra has initialized/moved P1, outside
        # its source groups, and before the later identity presentation events.
        self.blocks(f)[-1].extend(events)
        self.sync_groups(f)
        self.log("companions: players 2-4 can walk in %r" % f.name)

    SETPARAGRAPH = 84
    SETSTRING = 88

    def debug_dump(self):
        """Test aid: every half second write the multiplayer globals into the save file."""
        f = self.frame(OVERWORLD)
        ids = Ids(f)
        b0 = self.blocks(f)[0]
        ini = self.oi("obj ini", f)
        tmpl = None
        for g in b0:
            for a in g.actions:
                if a.object_info == ini and a.num == 87:  # ExtAct7: set value(item, value)
                    tmpl = a
                    break
            if tmpl:
                break
        acts = []
        for name in self.new_globals:
            a = clone(tmpl)
            a.params[0] = Param(a.params[0].code, expr(self._t_str("dbg_" + name)))
            a.params[1] = Param(a.params[1].code, expr(t_gv(self.global_index(name))))
            acts.append(a)
        every = cond(ids, -4, -8, params=[Param(2, struct.pack("<iih", 500, 0, 0)), Param(25, b"\0" * 6)])
        b0.insert(0, group([every], acts, line=self.next_line()))
        self.sync_groups(f)

    def test_jump(self):
        """Test aid: at startup jump to the frame number stored as testframe in [info]."""
        f = self.frames[0]
        ids = Ids(f)
        b0 = self.blocks(f)[0]
        ini = self.oi("obj ini", f)
        it = self.otype(ini)
        val = lambda: (struct.pack("<hhHHh", it, 82, 10, ini, 0), self._t_str("testframe"), t_close())
        b0.append(group([cond(ids, -3, -1, flags=0), c_compare(ids, val(), ">", (t_long(0),))],
                        [act(-3, 2, params=[p_expr(*val())])], line=self.next_line()))
        self.sync_groups(f)

    def global_index(self, name):
        count = struct.unpack_from("<h", self.globals_chunk, 0)[0]
        return count + self.new_globals.index(name)

    # ------------------------------------------------------------- utilities
    def find_sound_action(self, f, sound_name):
        """A copy of an existing 'play sample on channel' action for the named sound."""
        key = sound_name.encode("utf-16-le") + b"\0\0"
        for g in f.events.groups:
            for a in g.actions:
                if a.object_type == -2 and a.num == 11 and a.params and a.params[0].code == 6 \
                        and a.params[0].data[4:4 + len(key)] == key:
                    return clone(a)
        return None

    @staticmethod
    def find(blk, pred):
        for i, g in enumerate(blk):
            if pred(g):
                return i
        raise MergeError("expected event not found")

    @staticmethod
    def _objparam(c):
        for p in c.params:
            if p.code == 1:
                return struct.unpack_from("<hH", p.data, 0)[1]
        return None

    @staticmethod
    def _t_str(s):
        data = s.encode("utf-16-le") + b"\0\0"
        return struct.pack("<hhH", -1, 3, 6 + len(data)) + data

    def add_or_branch(self, ids, g, cond_index, replacement):
        """Add an OR branch to `g`: the branch holding condition `cond_index`, with that
        condition swapped for `replacement` (a list of conditions)."""
        branches, ornum = self.branches(g)
        br = next(b for b in branches if cond_index in b)
        nb = []
        for i in br:
            if i == cond_index:
                nb.extend(replacement)
            else:
                cc = clone(g.conditions[i])
                if cc.identifier:
                    cc.identifier = ids.take()
                nb.append(cc)
        g.conditions = g.conditions + [cond(ids, -1, ornum or -25, flags=0)] + nb

    # ------------------------------------------------------------------ output
    def write(self, out_dir):
        for f in self.frames:
            if any(not g.actions for g in f.events.groups):
                raise MergeError("compiled event without an action/no-op in %r" % f.name)
        os.makedirs(out_dir, exist_ok=True)
        objchunks = build_object_chunks(self.ultra, self.objs)
        frame_data = {}
        for f in self.frames:
            if id(f) in self.dirty:
                frame_data[id(f.chunk)] = f.rebuild({0x3338: f.instances_bytes(),
                                                     0x333D: f.events.serialize()})
        chunks = []
        for c in self.ultra.chunks:
            if c.id == 0x2234:
                chunks.append(NewChunk(c.id, c.flag, self.ext_chunk))
            elif c.id in objchunks:
                chunks.append(NewChunk(c.id, c.flag, objchunks[c.id]))
            elif c.id == 0x2232:
                chunks.append(NewChunk(c.id, c.flag, self.build_globals()))
            elif c.id == 0x3333 and id(c) in frame_data:
                chunks.append(NewChunk(c.id, c.flag, frame_data[id(c)]))
            else:
                chunks.append(c)
        src = self.ultra_dir
        for name in os.listdir(src):
            p = os.path.join(src, name)
            q = os.path.join(out_dir, name)
            if name == ULTRA_DAT:
                continue
            if name.lower().endswith(".cfg") and os.path.exists(q):
                continue  # keep the saves/options of an earlier merged copy
            if os.path.isdir(p):
                if not os.path.exists(q):
                    shutil.copytree(p, q)
            else:
                shutil.copy2(p, q)
        with open(os.path.join(out_dir, "Modules", "XBOXGamepad.mfx"), "wb") as fh:
            fh.write(self.mfx_bytes)
        write_game(self.ultra, os.path.join(out_dir, ULTRA_DAT), chunks)


def c_compare(ids, left, op, right):
    return cond(ids, -1, -3, params=[Param(22, expr(*left)), p_cmp(op, *right)])
