"""Bind battle input and reserve switching to the shared party's player slots."""
import struct

from .evb import (F_MAX, F_MIN, F_TOSTRING, Ids, act, a_set_gv, c_compare, c_gv, cond, expr, group, p_altval, p_cmp,
                  p_expr, t_altval, t_close, t_comma, t_ext, t_func, t_gv, t_long, t_objexp, t_op, t_str)
from .fusion import EXPR_PARAM_CODES, Param
from .party import clone_text


def referenced_objects(item):
    """Read object references at expression-token boundaries, including calls."""
    result = set()
    for p in item.params:
        if p.code not in EXPR_PARAM_CODES:
            continue
        offset = 2
        while offset + 6 <= len(p.data):
            typ, num, size = struct.unpack_from("<hhH", p.data, offset)
            if size < 6 or offset + size > len(p.data):
                break
            if typ > 0 and size >= 10:
                result.add((typ, struct.unpack_from("<H", p.data, offset + 6)[0]))
            offset += size
    return result


def replace_team_flag(parameter, switch, replacement):
    """Replace Flag(hud switch party, 0), preserving token boundaries.

    Fusion writes different cached object-list indices for the same object in
    different events. Those indices must not become part of a byte signature.
    """
    if parameter.code not in EXPR_PARAM_CODES:
        return 0
    data, offset, count = parameter.data, 2, 0
    parts = [data[:2]]
    tail = t_long(0) + t_close()
    while offset + 6 <= len(data):
        typ, num, size = struct.unpack_from("<hhH", data, offset)
        if size < 6 or offset + size > len(data):
            break
        end = offset + size
        if (typ == 2 and num == 13 and size == 10 and
                struct.unpack_from("<H", data, offset + 6)[0] == switch and
                data[end:end + len(tail)] == tail):
            parts.append(replacement)
            end += len(tail)
            count += 1
        else:
            parts.append(data[offset:end])
        offset = end
    parts.append(data[offset:])
    parameter.data = b"".join(parts)
    return count


def per_instance_team_condition(item):
    """Evaluate mixed-team indices separately for every selected object.

    Compare Alterable Value evaluates its variable index once before filtering
    the selection. Ultra could do that while all four slots used one team; a
    mixed party needs Compare Expression so each instance supplies its own team.
    The same applies to the common dynamic flag tests.
    """
    if item.num == -27 and len(item.params) == 2 and item.params[0].code == 53:
        index = item.params[0].data[2:-4]
        item.num = -45
        item.params[0] = p_expr(t_objexp(item.object_type, 30, item.object_info), index, t_close())
        return True
    if item.num in (-24, -25) and len(item.params) == 1:
        index = item.params[0].data[2:-4]
        is_set = int(item.num == -25)
        item.num = -45
        item.params = [p_expr(t_objexp(item.object_type, 13, item.object_info), index, t_close()),
                       p_cmp("=", t_long(is_set))]
        return True
    return False


def add_combat(m, otype, online):
    f = m.frames[4]
    b = m.blocks(f)[0]
    ids = Ids(f)
    G = m.G
    actor = m.oi("plr character", f)
    spawner = m.oi("spw player", f)
    health = m.oi("cnt life player", f)
    bars = m.oi("cnt life bar player", f)
    switch = m.oi("hud switch party", f)
    hitbox = m.oi("plr hitbox", f)
    moves = m.oi("mov button", f)
    marker = m.oi("btl current character", f)
    pending = G["swap_pending"] = m.alloc_global("mp_swap_pending")
    native = lambda n, *args: (t_ext(otype, n, online), *args, *((t_close(),) if args else ()))
    add = lambda cs, actions: group(cs, actions, line=m.next_line())
    flag = lambda oi, n: (t_objexp(2, 13, oi), t_long(n), t_close())

    # Ultra stores both teams' health and charge in each slot, but normally uses
    # one global team flag to address them. Replace that flag with the active
    # reserve for the selected slot. Actor, spawner and counter selections remain
    # intact; this is an expression, not an extension condition or nested loop.
    replacements = 0
    for g in list(f.events.groups):
        for item in g.conditions + g.actions:
            slot_tokens = None
            if item.object_info == actor and item.object_type == 2:
                slot_tokens = (t_altval(2, actor, 0),)
            elif item.object_info == spawner and item.object_type == 2:
                slot_tokens = (t_objexp(2, 46, spawner),)
            elif item.object_info in (health, bars) and item.object_type == 7:
                slot_tokens = (t_objexp(7, 46, item.object_info),)
            else:
                refs = referenced_objects(item)
                for typ, oi, tokens in ((2, actor, (t_altval(2, actor, 0),)),
                                        (2, spawner, (t_objexp(2, 46, spawner),)),
                                        (7, health, (t_objexp(7, 46, health),))):
                    if (typ, oi) in refs:
                        slot_tokens = tokens
                        break
            slot_tokens = slot_tokens or (t_gv(G["turn_slot"]),)
            changed = sum(replace_team_flag(p, switch, b"".join(native(22, *slot_tokens)))
                          for p in item.params)
            replacements += changed
            if changed and item in g.conditions and item.object_info in (actor, spawner, health, bars):
                per_instance_team_condition(item)

    # The legacy mouse handler must not run beside the network input handler.
    # Native host and guest clicks now use the same target ID and release latch.
    for g in list(f.events.groups):
        opens_turn = any(a.object_type == -1 and a.num == 14 and a.params and
                         "create button".encode("utf-16-le") in a.params[0].data for a in g.actions)
        if opens_turn:
            # Ultra normally displays only one team, so its two team-specific
            # busy flags never compete. Mixed A/B slots must share one turn.
            g.conditions = [c for c in g.conditions if not (c.object_info == switch and
                c.object_type == 2 and c.num == -24 and any(
                    t_ext(otype, 22, online) in p.data for p in c.params))]
            g.conditions.extend([
                cond(ids, 2, -24, actor, [p_expr(t_long(0))]),
                cond(ids, 2, -24, actor, [p_expr(t_long(1))]),
                cond(ids, 2, -24, switch, [p_expr(t_long(1))]),
                cond(ids, 2, -24, switch, [p_expr(t_long(2))]),
                cond(ids, 2, -32, moves, [p_cmp("=", t_long(0))]),
            ])
        if any(c.object_type == -1 and c.num == -16 and c.params and
               "create button".encode("utf-16-le") in c.params[0].data for c in g.conditions) or (
               any(a.object_info == moves and a.object_type == 2 and a.num == 24 for a in g.actions) and
               any(c.object_info == actor and c.object_type == 2 for c in g.conditions)):
            # Large or duplicated character sprites can overlap the marker.
            # The slot, not that overlap alone, identifies the acting character.
            g.conditions.append(cond(ids, 2, -27, actor, [p_altval(0), p_cmp("=", t_gv(G["turn_slot"]))]))
        if any(c.object_type >= 32 and c.num == -87 and m._objparam(c) == moves for c in g.conditions):
            g.conditions.append(c_compare(ids, native(19), "=", (t_long(1),)))
        if any(c.object_type >= 32 and c.num == -87 and m._objparam(c) == switch for c in g.conditions):
            branches, ornum = m.branches(g)
            out = []
            for indices in branches:
                if out:
                    out.append(cond(ids, -1, ornum or -25, flags=0))
                out.extend(g.conditions[i] for i in indices)
                out.append(c_compare(ids, native(23), "=", (t_long(0),)))
            g.conditions = out
        # Ultra's whole-team defeat check counts A/B, which can disagree with a
        # mixed co-op party. Use the same eight health pools for co-op defeat.
        if any(a.object_type == -3 and a.num == 2 and a.params and a.params[0].code == 26 and
               int.from_bytes(a.params[0].data, "little") == 2 for a in g.actions) and any(
               c.object_info == switch for c in g.conditions):
            g.conditions.append(c_compare(ids, native(23), "=", (t_long(0),)))

    touch = next(g for g in b if any(c.object_type >= 32 and c.num == -87 and m._objparam(c) == moves for c in g.conditions))
    k = b.index(touch)
    b[k:k] = [
        add([c_compare(ids, native(26), ">", (t_long(0),)),
             c_compare(ids, (t_gv(G["turn_slot"]),), "<>", native(26))],
            [a_set_gv(G["turn_slot"], *native(26)), a_set_gv(G["confirm_ready"], t_long(0))] + m.turn_owner_actions()),
        add([c_compare(ids, native(24, t_gv(G["turn_mask"])), ">=", (t_long(0),))],
            [a_set_gv(G["selected"], *native(24, t_gv(G["turn_mask"])))])
    ]

    # A co-op swap consumes only the current slot's turn. Preserve the original
    # actor exit/spawn behavior and charge cost, selecting one spawner instead
    # of respawning the entire party or changing its global team flag.
    primary_switch = next(g for g in b if len(g.actions) > 10 and any(
        c.object_type >= 32 and c.num == -87 and m._objparam(c) == switch for c in g.conditions))
    swap_groups = [
        add([c_compare(ids, native(23), "=", (t_long(1),)),
             c_compare(ids, native(25, t_gv(G["turn_mask"])), "=", (t_long(1),)),
             c_compare(ids, native(26), ">", (t_long(0),)),
             cond(ids, 2, -32, moves, [p_cmp(">", t_long(0))]),
             cond(ids, 7, -49, health, [p_cmp("=", t_gv(G["turn_slot"]))]),
             c_compare(ids, (t_objexp(7, 30, health), t_long(3), t_op("-"),
                             *native(22, t_gv(G["turn_slot"])), t_close()), ">", (t_long(0),))],
            [a_set_gv(pending, t_gv(G["turn_slot"])), act(otype, 90, online, [p_expr(t_gv(pending))]),
             act(2, 24, moves), act(2, 26, marker), act(2, 26, switch),
             act(2, 26, m.oi("spr run button", f)), act(3, 26, m.oi("hud hold button", f)),
             act(2, 31, switch, [p_altval(0), p_expr(t_long(3))]),
             act(2, 36, switch, [p_expr(t_long(1))]), act(2, 36, switch, [p_expr(t_long(2))])]),
        add([c_compare(ids, native(23), "=", (t_long(1),)), c_gv(ids, pending, "=", t_long(0)),
             c_compare(ids, native(38), ">", (t_long(0),))],
            [a_set_gv(pending, *native(38)), act(otype, 90, online, [p_expr(t_gv(pending))])]),
        add([c_gv(ids, pending, ">", t_long(0)), c_gv(ids, pending, "=", t_gv(G["turn_slot"]))],
            [act(2, 24, moves), act(2, 26, marker), act(2, 26, switch),
             act(2, 26, m.oi("spr run button", f)), act(3, 26, m.oi("hud hold button", f)),
             act(2, 31, switch, [p_altval(0), p_expr(t_long(3))]),
             act(2, 36, switch, [p_expr(t_long(1))]), act(2, 36, switch, [p_expr(t_long(2))]),
             a_set_gv(G["confirm_ready"], t_long(0))]),
        add([c_gv(ids, pending, ">", t_long(0)),
             cond(ids, 2, -27, actor, [p_altval(0), p_cmp("=", t_gv(pending))])],
            [act(2, 11, actor), act(2, 35, actor, [p_expr(t_long(0))])]),
        *[add([c_gv(ids, pending, ">", t_long(0)),
               c_compare(ids, native(22, t_gv(pending)), "=", (t_long(team),)),
               cond(ids, 2, -49, spawner, [p_cmp("=", t_gv(pending))])],
              [act(2, 31, spawner, [p_altval(2 - team), p_expr(t_long(0))])]) for team in [0, 1]],
        add([c_gv(ids, pending, ">", t_long(0)),
             cond(ids, 2, -49, spawner, [p_cmp("=", t_gv(pending))])],
            [act(2, 31, spawner, [p_altval(0), p_expr(t_long(4), t_op("+"), t_gv(pending), t_op("*"), t_long(5))]),
             act(2, 76, spawner, [Param(45, p_expr(t_str("spw player")).data)])]),
        add([c_gv(ids, pending, ">", t_long(0))],
            [a_set_gv(pending, t_long(0)), a_set_gv(G["confirm_ready"], t_long(0))]),
        add([c_compare(ids, native(23), "=", (t_long(1),)),
             cond(ids, 2, -27, switch, [p_altval(0), p_cmp(">", t_long(4))])],
            [act(2, 31, switch, [p_altval(0), p_expr(t_long(4))])]),
    ]
    k = b.index(primary_switch)
    b[k:k] = swap_groups
    b[m.top_count:m.top_count] = [add([cond(ids, -1, -1)], [act(otype, 89, online, [
        p_expr(t_gv(G["players"])), p_expr(t_gv(G["turn_slot"])), p_expr(*flag(hitbox, 1)),
        p_expr(t_gv(G["keyboard_p1"])), p_expr(t_gv(G["turn_owner"]))])])]
    for slot in range(1, 5):
        b.insert(m.top_count + slot, add([cond(ids, 7, -49, health, [p_cmp("=", t_long(slot))])], [
            act(otype, 92, online, [p_expr(t_long(slot)),
                *(p_expr(t_objexp(7, 30, health), t_long(index), t_close()) for index in [2, 3, 0, 1])])]))
    b.append(add([c_compare(ids, native(23), "=", (t_long(1),)),
                  c_compare(ids, native(37), "=", (t_long(0),))],
                 [act(-3, 2, params=[p_expr(t_long(10))])]))
    status = clone_text(m, f, "MP battle player and character", 20, 400, 220, 55)
    name = (t_func(19), t_objexp(3, 81, status), t_comma(), t_func(22), t_objexp(3, 81, status),
            t_close(), t_op("-"), t_long(12), t_close())
    b += [
        add([cond(ids, 2, -32, moves, [p_cmp(">", t_long(0))]),
             cond(ids, 2, -27, actor, [p_altval(0), p_cmp("=", t_gv(G["turn_slot"]))]),
             c_compare(ids, flag(actor, 2), "=", native(22, t_gv(G["turn_slot"])))], [
            act(3, 84, status, [p_expr(t_objexp(2, 14, actor), t_op("-"), t_long(10))]),
            act(3, 88, status, [Param(45, expr(t_str("P"), t_op("+"), t_func(F_TOSTRING),
                t_gv(G["turn_owner"]), t_op("+"), t_long(1), t_close(), t_op("+"), t_str("  Slot "),
                t_op("+"), t_func(F_TOSTRING), t_gv(G["turn_slot"]), t_close(), t_op("+"), t_str("\n"), t_op("+"), *name))]),
            act(3, 27, status)]),
        add([cond(ids, 2, -32, moves, [p_cmp("=", t_long(0))])], [act(3, 26, status)]),
    ]
    # The stock relative-position parent can still name an actor sliding out
    # after an individual reserve swap. Resolve the one active slot explicitly,
    # using numeric X/Y actions, and keep its four move buttons in the viewport.
    bounded = lambda value, lo, hi: (t_func(F_MAX), t_long(lo), t_comma(), t_func(F_MIN),
                                    *value, t_comma(), t_long(hi), t_close(), t_close())
    b.append(add([c_compare(ids, native(23), "=", (t_long(1),)),
                  cond(ids, 2, -32, moves, [p_cmp(">", t_long(0))]),
                  cond(ids, 2, -27, actor, [p_altval(0), p_cmp("=", t_gv(G["turn_slot"]))]),
                  cond(ids, 2, -24, actor, [p_expr(t_long(0))]),
                  cond(ids, 2, -24, actor, [p_expr(t_long(1))]),
                  c_compare(ids, flag(actor, 2), "=", native(22, t_gv(G["turn_slot"])))], [
        act(2, 2, marker, [p_expr(t_objexp(2, 11, actor))]),
        act(2, 3, marker, [p_expr(t_objexp(2, 1, actor), t_op("+"), t_long(8))]),
        act(2, 2, moves, [p_expr(*bounded((t_objexp(2, 11, actor), t_op("-"), t_long(206)), 16, 440),
                                t_op("+"), t_long(10), t_op("*"), t_altval(2, moves, 20))]),
        act(2, 3, moves, [p_expr(*bounded((t_objexp(2, 1, actor), t_op("-"), t_long(190)), 100, 280),
                                t_op("+"), t_long(45), t_op("*"), t_altval(2, moves, 20))]),
    ]))
    for g in b:
        for a in g.actions:
            if (a.object_type == -1 and a.num == 27 and len(a.params) == 2 and
                    struct.unpack_from("<h", a.params[0].data)[0] == G["turn_owner"] and
                    t_op("mod") in a.params[1].data):
                a.params[1] = p_expr(*native(36, t_gv(G["turn_slot"])))
    m.sync_groups(f)
    m.log("co-op combat: guest mouse targets, slot ownership and %d team-selector expressions" % replacements)
