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


def test_game(path):
    g = Game(path)
    objs = parse_objects(g)
    frames = parse_frames(g)
    check(g.name == "FNaF World Ultra", "merged game name")
    check(any(o.name == "MP Gamepad" for o in objs), "gamepad object present")
    online = next((o for o in objs if o.name == "MP Online"), None)
    if online is not None:
        for f in frames:
            first = f.events.groups[0]
            check(any(a.object_type == online.type and a.object_info == online.index and a.num == 80
                      for a in first.actions), "online tick precedes game events in %r" % f.name)
            callbacks = [c for g in f.events.groups for c in g.conditions
                         if c.object_info == online.index and c.object_type == online.type
                         and (-81 - c.num) in (18, 19, 20, 23, 24, 26)]
            check(all(not c.flags & 32 for c in callbacks),
                  "native callbacks registered as triggered events in %r" % f.name)
            lines = [g.line for g in f.events.groups if g.conditions and
                     g.conditions[0].object_info == online.index and g.conditions[0].object_type == online.type]
            check(all(n > 0 for n in lines) and len(lines) == len(set(lines)),
                  "online callbacks have distinct event identifiers in %r" % f.name)
    pc = g.chunk(0x2242)
    tc = g.chunk(0x222F)
    stored = struct.unpack("<I", pc.decode(g))[0]
    check(stored == make_pame_checksum(bytes(g.data[tc.offset:pc.offset])), "protection checksum valid")
    for f in frames:
        check(f.events.serialize() == f.sub(0x333D).decode(g), "events of %r re-read" % f.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    a = ap.parse_args()
    test_checksum()
    test_chunks()
    test_events()
    if a.game:
        test_game(a.game)
    print("all good")


if __name__ == "__main__":
    main()
