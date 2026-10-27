"""First-selected-character avatars and group dialogue staging using Ultra art."""

import struct

from .evb import (F_MIN, Ids, act, a_set_gv, c_compare, c_gv, clone, cond, group, p_altval, p_cmp, p_expr,
                  t_altval, t_close, t_comma, t_double, t_func, t_gv, t_long,
                  t_objexp, t_op, t_str, t_ext, t_open)
from .party import clone_active, clone_text


def add_identity(m):
    G = m.G
    online = next(o for o in m.objs if o.name == "MP Online")
    pose = lambda index: t_ext(online.type, index, online.index)
    primary = [m.alloc_global("mp_primary_%d" % n) for n in range(1, 5)]
    G.update({"primary_%d" % n: gv for n, gv in enumerate(primary, 1)})
    f = m.frames[3]
    ids = Ids(f)
    available = m.oi("spr available", f)
    b = m.blocks(f)[0]
    # Record accepted edits immediately, including a pick made just before the
    # host starts. The scene jump can stop the later Always events that tick.
    for g in b:
        row = next((struct.unpack_from("<i", c.params[0].data, 8)[0] for c in g.conditions
                    if c.object_info == available and c.object_type == 2 and c.num == -49 and
                    c.params and len(c.params[0].data) >= 12), 0)
        value = next((a.params[1] for a in g.actions if a.object_info == available and
                      a.object_type == 2 and a.num == 31 and len(a.params) == 2 and
                      struct.unpack_from("<h", a.params[0].data)[0] == 0), None)
        if 1 <= row <= 4 and value is not None:
            save_identity = a_set_gv(primary[row - 1], t_long(0))
            save_identity.params[1] = clone(value)
            g.actions.append(save_identity)
    # Keep identity independent of the currently active reserve and of character
    # IDs shared by duplicate picks. Each player's first owned slot is 1..4.
    for slot, gv in enumerate(primary, 1):
        b.append(group([cond(ids, 2, -49, available, [p_cmp("=", t_long(slot))]),
                        cond(ids, 2, -27, available, [p_altval(0), p_cmp(">", t_long(0))])],
                       [a_set_gv(gv, t_altval(2, available, 0))], line=m.next_line()))
    m.sync_groups(f)

    profile_group = next(clone(a) for g in f.events.groups for a in g.actions
                         if a.object_type >= 32 and a.num == 80 and a.params and
                         "fnafw".encode("utf-16-le") in a.params[0].data)
    avatars = {}
    for frame_index in [4, 5, 6, 7, 8, 18, 19, 20, 21]:
        f = m.frames[frame_index]
        ids = Ids(f)
        b = m.blocks(f)[0]
        world = frame_index in range(4, 9) or frame_index == 20
        hit = m.oi("plr hitbox", f) if world else None
        actors = []
        add = lambda conditions, actions: b.append(group(conditions, actions, line=m.next_line()))
        coop = lambda: c_compare(ids, (t_gv(G["players"]), t_op("+"), t_gv(G["online_session"])), ">", (t_long(1),))
        solo = lambda: c_compare(ids, (t_gv(G["players"]), t_op("+"), t_gv(G["online_session"])), "<=", (t_long(1),))
        # Read committed selections on entry. Cancelling the party editor must
        # not leave an unsaved draft as the player's exploration/NPC identity.
        ini = m.oi("obj ini", f)
        select_profile = clone(profile_group)
        select_profile.object_info, select_profile.object_type = ini, m.otype(ini)
        add([cond(ids, -3, -1, flags=0)], [select_profile] + [
            a_set_gv(gv, t_ext(m.otype(ini), 2, ini), t_str("s%d" % slot), t_close())
            for slot, gv in enumerate(primary, 1)])
        for player in range(1, 5):
            oi = clone_active(m, f, m.oi("plr character"), "MP first character P%d" % player, -400, -400)
            actors.append(oi)
            label = clone_text(m, f, "MP player label P%d" % player, -400, -400, 100 if not world else 55, 18)
            npc = "spr fredbear" if frame_index == 19 else "spr animdude" if frame_index == 18 else "spr creator"
            layer = next(i.layer for i in f.instances if i.object_info == (hit if world else m.oi(npc, f)))
            for item in f.instances:
                if item.object_info in [oi, label]:
                    item.layer = layer
            active = [coop(), c_gv(ids, G["players"], ">=", t_long(player))]
            if world:
                body = hit if player == 1 else m.oi("mp hitbox %d" % player, f)
                active.append(cond(ids, 2, -24, hit, [p_expr(t_long(1))]))
                x = (t_objexp(2, 11, body),)
                y = (t_objexp(2, 1, body), t_op("+"), t_long(12))
                width, height = (t_long(44),), 46
            else:
                center = 500 if frame_index in [18, 19] else 400
                gap = 560 if frame_index in [18, 19] else 640
                spacing = (t_func(F_MIN), t_long(180), t_comma(), t_long(gap), t_op("/"), t_gv(G["players"]), t_close())
                x = (t_long(center), t_op("+"), t_open(), t_long(2 * player - 1), t_op("-"),
                     t_gv(G["players"]), t_close(), t_op("*"), *spacing, t_op("/"), t_long(2))
                y = (t_long(440),)
                width, height = (*spacing, t_op("-"), t_long(10)), 185
            add(active, [
                act(2, 4, oi),
                act(2, 17, oi, [p_expr(t_ext(online.type, 42, online.index), t_long(player), t_comma(), t_gv(primary[player - 1]), t_close(), t_op("+"), t_long(10))]),
                act(2, 40, oi, [p_expr(t_long(0))]),
                act(online.type, 93, online.index, [p_expr(t_long(oi)), p_expr(*x), p_expr(*y),
                                                    p_expr(*width), p_expr(t_long(height))]),
                act(2, 85, oi, [p_expr(pose(39)), p_expr(t_long(1))]),
                act(2, 2, oi, [p_expr(pose(40))]), act(2, 3, oi, [p_expr(pose(41))]),
                act(2, 27, oi),
                act(3, 88, label, [p_expr(t_str("P%d" % player))]),
                act(3, 2, label, [p_expr(*x, t_op("-"), t_long(10))]),
                act(3, 3, label, [p_expr(*y, t_op("+"), t_long(2))]),
                act(3, 27, label),
            ])
            hidden = [act(2, 26, oi), act(3, 26, label)]
            add([solo()], hidden)
            add([c_gv(ids, G["players"], "<", t_long(player))], hidden)
            if world:
                add([cond(ids, 2, -25, hit, [p_expr(t_long(1))])], hidden)
        avatars[frame_index] = actors
        original = [m.oi("plr overworld" if frame_index == 4 else
                        "spr player" if frame_index == 20 else "plr sprite", f),
                    *(m.oi("mp walker %d" % n, f) for n in [2, 3, 4])] if world else [
                        m.oi("spr player" if frame_index == 21 else "plr character", f)]
        # Keep the original actor alive for Ultra's story/animation callbacks.
        # Only its drawing is replaced during co-op.
        add([coop()], [act(2, 26, oi) for oi in original])
        if world:
            add([solo(), cond(ids, 2, -24, hit, [p_expr(t_long(1))])], [act(2, 27, original[0])])
        else:
            add([solo()], [act(2, 27, original[0])])
        m.sync_groups(f)
    m.log("player identity: selected primary characters in exploration/clock rooms and group NPC scenes")
    return avatars
