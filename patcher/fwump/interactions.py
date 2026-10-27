"""Let each exploration hitbox activate Ultra's shared world interactions."""
import struct

from .evb import Ids, c_gv, clone, t_long


def add_interactions(m):
    count = 0
    for frame_index in range(4, 9):
        f = m.frames[frame_index]
        ids = Ids(f)
        hit = m.oi("plr hitbox", f)
        body = m.oi("plr overworld" if frame_index == 4 else
                    "spr player" if frame_index == 20 else "plr sprite", f)
        companions = [m.oi("mp hitbox %d" % player, f) for player in (2, 3, 4)]
        # The original event's actions still run once. Only its positive
        # collision/overlap trigger gains alternatives. Negative overlaps and
        # movement probes must retain their original all-clear semantics.
        for g in list(f.events.groups):
            hits = [i for i, c in enumerate(g.conditions)
                    if c.object_type == 2 and c.num in (-4, -14) and not c.other_flags & 1
                    and len(c.params) == 1 and c.params[0].code == 1
                    and (c.object_info in (hit, body) or m._objparam(c) in (hit, body))]
            if not hits:
                continue
            if len(hits) != 1:
                raise RuntimeError("Ambiguous exploration interaction in %r event %d" % (f.name, g.line))
            index = hits[0]
            source = g.conditions[index]
            for player, companion in zip((2, 3, 4), companions):
                alternative = clone(source)
                alternative.identifier = ids.take()
                alternative.object_info_list = 0
                if source.object_info in (hit, body):
                    alternative.object_info = companion
                else:
                    data = bytearray(alternative.params[0].data)
                    struct.pack_into("<H", data, 2, companion)
                    alternative.params[0].data = bytes(data)
                m.add_or_branch(ids, g, index, [
                    c_gv(ids, m.G["p%d_active" % player], "=", t_long(1)), alternative])
            # Logical OR merges the source target's selected-object list before
            # the original chest/reward/transition actions execute.
            g.flags |= 0x1400
            count += 1
        m.sync_groups(f)
    m.log("shared world interactions accept every player at %d triggers" % count)
