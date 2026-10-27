#!/usr/bin/env python3
"""Self-tests for the patcher's file-format code.

  python3 selftest.py                 # no game files needed
  python3 selftest.py --game <.dat>   # also verify a merged game file
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fwump import evb  # noqa: E402
from fwump.ccn import Decrypter, Game, read_chunks  # noqa: E402
from fwump.checksum import make_checksum, make_pame_checksum  # noqa: E402
from fwump.fusion import Events, pack_chunk, parse_frames, parse_objects  # noqa: E402
from fwump.online import gate_keyboard  # noqa: E402
from fwump.combat import replace_team_flag  # noqa: E402
from fwump.minigames import remap_item  # noqa: E402


class FakeGame:
    build = 295

    def __init__(self):
        self.decrypter = Decrypter("FNaF World Ultra", "2016 Scott Cawthon", "x.mfa")


def check(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)
    print("ok  ", what)


def test_checksum():
    check(make_checksum(b"") == 0, "checksum of empty data")
    data = bytes(range(256)) * 3 + b"\x01\x02\x03"
    c = make_checksum(data)
    check(make_pame_checksum(data) == (c & 0xFFFFFF00) | ((c & 0xFF) ^ 13), "protection checksum xor")


def test_chunks():
    g = FakeGame()
    payload = b"hello world" * 50
    for flag in (0, 1, 2, 3):
        for cid in (0x2245, 0x333D):
            raw = pack_chunk(cid, flag, payload, g)
            chunks, end = read_chunks(raw, 0, stop_at_last=False)
            check(len(chunks) == 1 and chunks[0].decode(g) == payload and end == len(raw),
                  "chunk round trip flag %d id %04x" % (flag, cid))


def test_events():
    # a frame-like event list: group header, two groups, a pointer to the second
    class F:
        pass
    blob = (b"ER>>" + struct.pack("<hhh", 1000, 3, 1) + struct.pack("<17h", *range(17)) + struct.pack("<h", 0) +
            b"ERop" + struct.pack("<i", 1) + b"ERes" + struct.pack("<i", 0) + b"ERev" + struct.pack("<i", 0) +
            b"<<ER")
    ev = Events(blob)
    fr = F()
    fr.events = ev
    ids = evb.Ids(fr)
    grp_param = evb.Param(38, struct.pack("<HH", 0, 7) + b"\0" * 194)
    g_newgroup = evb.group([evb.cond(ids, -1, -10, params=[grp_param])], [evb.act(-1, 0)])
    ptr = evb.Param(39, struct.pack("<ih", 12345, 7))
    g_act = evb.group([evb.c_always(ids)], [evb.act(-1, 6, params=[ptr])])
    blk = [s for s in ev.sections if s[0] == b"ERev"][0][1]
    blk.extend([g_act, evb.group([evb.c_always(ids)], [evb.a_set_gv(3, evb.t_long(5))]), g_newgroup])
    data = ev.serialize()
    again = Events(data)
    check(again.serialize() == data, "event list round trip")
    # the pointer must now be the distance from the parameter to the group
    start_of_target = len(g_act.serialize()) + len(blk[1].serialize())
    param_pos = 16 + len(g_act.conditions[0].serialize()) + 14
    p, gid = struct.unpack_from("<ih", ptr.data, 0)
    check(gid == 7 and p == start_of_target - param_pos, "group pointer recomputed (%d)" % p)
    check(evb.a_set_gv(3, evb.t_long(5)).num == 27 and evb.a_set_gv(3, evb.t_gv(1)).num == 3,
          "constant vs expression global actions")


def test_keyboard_focus():
    class F:
        pass
    frame = F()
    frame.events = F()
    frame.events.groups = []
    ids = evb.Ids(frame)
    key = lambda vk, negate=False: evb.cond(ids, -6, -2, params=[
        evb.Param(14, struct.pack("<HH", vk, 0))], other=int(negate))
    keyboard, release = key(87), key(68, True)
    pad = evb.cond(ids, 50, -93, 700, [evb.p_expr(evb.t_long(1))])
    escape = evb.cond(ids, -6, -1, params=[evb.Param(14, struct.pack("<HH", 27, 0))])
    event = evb.group([keyboard, release, evb.cond(ids, -1, -25), pad,
                       key(68, True), evb.cond(ids, -1, -25), escape], [])
    gate_keyboard(event, ids, 50, 700)
    from fwump.merge import Merger
    branches, _ = Merger.branches(event)
    parts = [[event.conditions[i] for i in b] for b in branches]
    check(any(c.object_type == -1 and c.num == -3 and evb.t_ext(50, 19, 700) in c.params[0].data for c in parts[0]) and
          all(not any(evb.t_ext(50, 19, 700) in p.data for p in c.params) for b in parts[1:] for c in b),
          "only mapped legacy keyboard branches require offline focused input")
    check(all(any(c.object_type == -1 and c.num == -3 and
              c.params[0].data == evb.p_expr(evb.t_ext(50, 20, 700), evb.t_long(68), evb.t_close()).data for c in b) for b in parts[:2]),
          "keyboard and pad branches both resolve key releases after changing focus")
    check(parts[0][0] is keyboard and parts[1][0] is pad and parts[2] == [escape],
          "native pad input and original menu keys retain their branches")


def test_slot_teams():
    for cache in (0, 2, 10, -1):
        flag = evb.t_objexp(2, 13, 315)
        flag = flag[:-2] + struct.pack("<h", cache)
        parameter = evb.p_expr(flag, evb.t_long(0), evb.t_close(), evb.t_op("+"), evb.t_long(4))
        replacement = evb.t_ext(46, 22, 1353) + evb.t_long(3) + evb.t_close()
        check(replace_team_flag(parameter, 315, replacement) == 1 and
              parameter.data == evb.p_expr(replacement, evb.t_op("+"), evb.t_long(4)).data,
              "per-slot teams handle Fusion object cache %d" % cache)
    text = "Team flag bytes " + (evb.t_objexp(2, 13, 315) + evb.t_long(0) + evb.t_close()).decode("utf-16-le")
    parameter = evb.p_expr(evb.t_str(text))
    before = parameter.data
    check(replace_team_flag(parameter, 315, b"test") == 0 and parameter.data == before,
          "team rewrites leave string literals intact")


def test_game(path):
    g = Game(path)
    objs = parse_objects(g)
    frames = parse_frames(g)
    check(g.name == "FNaF World Ultra", "merged game name")
    check(any(o.name == "MP Gamepad" for o in objs), "gamepad object present")
    online = next((o for o in objs if o.name == "MP Online"), None)
    if online is not None:
        for f in frames:
            check(all(group.actions for group in f.events.groups),
                  "compiled events retain an action or a no-op in %r" % f.name)
            markers = [group for group in f.events.groups if any(
                c.object_type == -1 and c.num == -42 for c in group.conditions)]
            check(all(len(group.conditions) == 1 for group in markers),
                  "child event boundaries retain their structural layout in %r" % f.name)
            first = f.events.groups[0]
            check(any(a.object_type == online.type and a.object_info == online.index and a.num == 80
                      for a in first.actions), "online tick precedes game events in %r" % f.name)
            callbacks = [c for g in f.events.groups for c in g.conditions
                         if c.object_info == online.index and c.object_type == online.type
                         and (-81 - c.num) in (18, 19, 20, 23, 24, 26, 27, 28, 29, 30, 31)]
            check(all(not c.flags & 32 for c in callbacks),
                  "native callbacks registered as triggered events in %r" % f.name)
            lines = [g.line for g in f.events.groups if g.conditions and
                     g.conditions[0].object_info == online.index and g.conditions[0].object_type == online.type]
            check(all(n > 0 for n in lines) and len(lines) == len(set(lines)),
                  "online callbacks have distinct event identifiers in %r" % f.name)
            camera = [a for group in f.events.groups
                      if any(c.object_type == online.type and c.num == -97 and c.other_flags & 1
                             for c in group.conditions) for a in group.actions if a.object_type == -3]
            check([a.num for a in camera] == [8, 9] and all(len(a.params) == 1 and a.params[0].code == 22 for a in camera),
                  "guest camera uses numeric X/Y scroll actions in %r" % f.name)
    battle = next(f for f in frames if f.name == "5: Overworld")
    if online is not None:
        wait = next(group for group in battle.events.groups if any(
            c.object_type == -1 and c.num == -16 and c.params and
            "battlewait".encode("utf-16-le") in c.params[0].data for c in group.conditions))
        check(any(c.object_type == -1 and c.num == -3 and
              evb.t_ext(online.type, 18, online.index) in c.params[0].data for c in wait.conditions) and
              not any(c.object_type == online.type and c.num == -97 for c in wait.conditions),
              "encounter loop authority guard preserves Fusion object selection")
        cleanup = [g for g in battle.events.groups if any(
            c.object_type == 2 and c.object_info == 305 and c.num == -32 and c.params and
            c.params[0].data == evb.p_cmp("=", evb.t_long(3)).data for c in g.conditions)
            and any(a.object_type == 2 and a.object_info == 305 and a.num == 24 for a in g.actions)
            and not any(a.object_type == online.type for a in g.actions)]
        check(cleanup and all(not any(c.object_type == 2 and c.object_info == 68 for c in g.conditions)
                              for g in cleanup),
              "attack-button cleanup remains independent of a living acting character")
        mixed_indices = [c for g in battle.events.groups for c in g.conditions
                         if c.object_info in (68, 107, 235, 238) and
                         ((c.num == -27 and c.params[0].code == 53) or c.num in (-24, -25)) and
                         any(evb.t_ext(online.type, 22, online.index) in p.data for p in c.params)]
        check(not mixed_indices,
              "mixed-team turn and health conditions evaluate the team per instance")
    turn = next(group for group in battle.events.groups if any(
        a.object_type == -1 and a.num == 14 and a.params and
        "create button".encode("utf-16-le") in a.params[0].data for a in group.actions))
    prefix = turn.actions[:6]
    check(all(a.object_type == -1 and a.num in (3, 27) for a in prefix) and
          prefix[0].params[1].data.count(evb.t_altval(2, 68, 0)) == 1 and
          prefix[5].params[1].data.count(evb.t_op("^")) == 1,
          "turn owner and controller mask assigned before creating attack buttons without a nested loop")
    ready = struct.unpack_from("<H", prefix[2].params[0].data)[0]
    confirms = [group for group in battle.events.groups if any(
        c.object_type >= 32 and c.num == -82 for c in group.conditions) and any(
        a.object_type == 2 and a.object_info == 305 and a.num == 24 for a in group.actions)]
    check(len(confirms) == 1 and any(c.object_type == -1 and c.num == -28 and
          c.params[0].data == evb.p_global(ready).data and c.params[1].data == evb.p_cmp("=", evb.t_long(1)).data
          for c in confirms[0].conditions), "confirm requires the new turn's button-release latch")
    if online is not None:
        clicks = [group for group in battle.events.groups if any(c.object_type >= 32 and c.num == -87 and
                  any(p.code == 1 and struct.unpack_from("<H", p.data, 2)[0] == 305 for p in c.params)
                  for c in group.conditions)]
        check(bool(clicks) and all(any(c.object_type == -1 and c.num == -3 and
              evb.t_ext(online.type, 21, online.index) in c.params[0].data for c in group.conditions) and
              not any(c.object_type == online.type and c.num == -113 for c in group.conditions)
              for group in clicks), "mouse ownership guards preserve the acting character selection")
        f9 = [group for group in battle.events.groups if any(c.object_type == -6 and c.num == -1 and
              any(p.code == 14 and struct.unpack_from("<H", p.data)[0] == 120 for p in c.params)
              for c in group.conditions)]
        check(bool(f9) and all(any(c.object_type == online.type and c.num == -103 and c.other_flags & 1
              for c in group.conditions) for group in f9), "F9 keyboard reassignment is disabled in native sessions")
    pc = g.chunk(0x2242)
    tc = g.chunk(0x222F)
    stored = struct.unpack("<I", pc.decode(g))[0]
    check(stored == make_pame_checksum(bytes(g.data[tc.offset:pc.offset])), "protection checksum valid")
    for f in frames:
        check(f.events.serialize() == f.sub(0x333D).decode(g), "events of %r re-read" % f.name)


def test_participant_references():
    source, target = 1210, 1600
    embedded = chr(source) + " keeps its text"
    item = evb.act(2, 31, source, [evb.p_altval(1), evb.p_expr(
        evb.t_altval(2, source, 2), evb.t_op("+"), evb.t_long(source), evb.t_op("+"), evb.t_str(embedded))])
    remap_item(item, {source: target})
    check(item.object_info == target and evb.t_altval(2, target, 2) in item.params[1].data,
          "participant actor and expression references remap together")
    check(evb.t_long(source) in item.params[1].data and evb.t_str(embedded) in item.params[1].data,
          "participant remapping preserves numeric constants and string contents")
    overlap = evb.act(2, -4, 32772, [evb.p_object(2, source)])
    remap_item(overlap, {source: target})
    check(overlap.object_info == target and overlap.params[0].data == evb.p_object(2, 32772).data,
          "participant collision owners retain the shared hazard target")
    children = evb.act(-1, 43, 65535, [evb.Param(69, struct.pack("<4i", 2, source, 100, -1))])
    remap_item(children, {source: target})
    check(children.params[0].data == struct.pack("<4i", 2, target, 100, -1),
          "participant child selections retain their count and shared objects")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    a = ap.parse_args()
    test_checksum()
    test_chunks()
    test_events()
    test_keyboard_focus()
    test_slot_teams()
    test_participant_references()
    if a.game:
        test_game(a.game)
    print("all good")


if __name__ == "__main__":
    main()
