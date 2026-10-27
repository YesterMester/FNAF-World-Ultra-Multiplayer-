"""Participant-specific adapters that retain Ultra's original stage physics."""

import struct

from .evb import (
    F_MAX,
    F_MIN,
    F_TOSTRING,
    Ids,
    act,
    a_add_gv,
    a_set_gv,
    c_compare,
    c_gv,
    clone,
    cond,
    group,
    p_altval,
    p_cmp,
    p_expr,
    p_global,
    p_object,
    t_altval,
    t_close,
    t_comma,
    t_func,
    t_gv,
    t_long,
    t_objexp,
    t_op,
    t_str,
)
from .fusion import EXPR_PARAM_CODES
from .party import clone_active, clone_text


def remap_item(item, mapping):
    """Rewrite actual object fields and expression tokens, never raw substrings."""
    # Bind a new collider through the condition's own OI. This gives Fusion an
    # explicit participant selection while retaining the shared hazard group.
    if (
        item.object_type == 2
        and item.num in (-4, -14)
        and not item.other_flags & 1
        and item.object_info not in mapping
        and len(item.params) == 1
        and item.params[0].code == 1
    ):
        target = struct.unpack_from("<H", item.params[0].data, 2)[0]
        if target in mapping:
            shared = item.object_info
            item.object_info, item.object_info_list = mapping[target], 0
            item.params = [p_object(2, shared)]
            return
    if item.object_type > 0 and item.object_info in mapping:
        item.object_info = mapping[item.object_info]
    item.object_info_list = 0
    for p in item.params:
        data = bytearray(p.data)
        if p.code in EXPR_PARAM_CODES:
            offset = 2
            while offset + 6 <= len(data):
                typ, num, size = struct.unpack_from("<hhH", data, offset)
                if size < 6 or offset + size > len(data):
                    break
                if typ > 0 and size >= 10:
                    oi = struct.unpack_from("<H", data, offset + 6)[0]
                    if oi in mapping:
                        struct.pack_into("<Hh", data, offset + 6, mapping[oi], 0)
                offset += size
        elif p.code == 1 and len(data) >= 8:
            oi = struct.unpack_from("<H", data, 2)[0]
            if oi in mapping:
                struct.pack_into(
                    "<Hh",
                    data,
                    2,
                    mapping[oi],
                    item.object_type if item.object_type > 0 else 2,
                )
        elif p.code in (9, 16, 18):
            # Create / relative position / shoot: parent object at byte zero.
            oi = struct.unpack_from("<H", data)[0]
            if oi in mapping:
                struct.pack_into("<H", data, 0, mapping[oi])
            if p.code == 9 and len(data) >= 26:
                oi = struct.unpack_from("<H", data, 24)[0]
                if oi in mapping:
                    struct.pack_into("<H", data, 24, mapping[oi])
        elif p.code == 69:
            # Child-event selected-object list. OI entries are int32, terminated
            # by -1; the first int32 is the list length, not an object handle.
            for offset in range(4, len(data) - 3, 4):
                oi = struct.unpack_from("<i", data, offset)[0]
                if oi in mapping:
                    struct.pack_into("<i", data, offset, mapping[oi])
        p.data = bytes(data)


def add_minigames(m):
    m.minigame_avatars = {}
    m.minigame_buttons = {}
    add_clock(m)
    add_rainbow(m)
    add_fighters(m)
    add_fishing(m)
    add_space(m)
    add_foxy_trial(m)


def participant_copy(m, ids, original, mapping):
    copied = clone(original)
    for c in copied.conditions:
        if c.identifier:
            c.identifier = ids.take()
    for item in copied.conditions + copied.actions:
        remap_item(item, mapping)
    copied.flags &= ~0x2000
    copied.line = m.next_line()
    return copied


def guard_conditions(m, ids, g, guards):
    """Apply a participant guard to every original logical OR branch."""
    branches, ornum = m.branches(g)
    out = []
    for branch in branches:
        if out:
            out.append(cond(ids, -1, ornum, flags=0))
        out.extend(g.conditions[i] for i in branch)
        for original in guards:
            c = clone(original)
            if c.identifier:
                c.identifier = ids.take()
            out.append(c)
    g.conditions = out


def clone_participants(m, f, personal, prefix):
    mappings = [{oi: oi for oi in personal}]
    for player in (2, 3, 4):
        mapping = {}
        for oi in personal:
            placed = next(i for i in f.instances if i.object_info == oi)
            copied = clone_active(
                m,
                f,
                oi,
                "%s P%d %s" % (prefix, player, m.objs[oi].name),
                placed.x,
                placed.y,
            )
            next(i for i in f.instances if i.object_info == copied).layer = placed.layer
            mapping[oi] = copied
        mappings.append(mapping)
    return mappings


def add_clock(m):
    f = m.frames[20]
    source = list(f.events.groups)
    if not (source[8].flags & 0x40 and source[22].conditions[0].num == -42):
        raise RuntimeError("Unrecognized clock puzzle event tree")
    ids = Ids(f)
    b = m.blocks(f)[-1]
    for player in (2, 3, 4):
        mapping = {87: m.oi("mp hitbox %d" % player, f)}
        for original in [*source[8:23], source[23], source[24]]:
            copied = clone(original)
            for index, c in enumerate(copied.conditions):
                if c.identifier:
                    c.identifier = ids.take()
                if c.object_info == 394 and c.object_type == 2 and c.num == -25:
                    replacement = c_gv(ids, m.G["p%d_moving" % player], "=", t_long(1))
                    copied.conditions[index] = replacement
            for item in copied.conditions + copied.actions:
                remap_item(item, mapping)
            if not copied.flags & 0x8000:
                copied.conditions.append(
                    c_gv(ids, m.G["p%d_active" % player], "=", t_long(1))
                )
            copied.line = m.next_line()
            b.append(copied)
    m.sync_groups(f)
    m.log(
        "clock co-op: each walker can push/collect puzzle targets against the shared timer/result"
    )


def add_rainbow(m):
    f = m.frames[26]
    source = list(f.events.groups)
    if len(source) != 239 or not any(
        a.object_info == 1210 and a.num == 35 for a in source[65].actions
    ):
        raise RuntimeError("Unrecognized Rainbow stage events")
    ids = Ids(f)
    b = m.blocks(f)[-1]
    G = m.G
    deaths = G["rainbow_deaths"] = m.alloc_global("mp_rainbow_team_deaths")
    actor, vertical, horizontal, collision = 1192, 1210, 1217, 1218
    personal = (actor, vertical, horizontal, collision, 1212, 1213, 1214)
    mappings = [{oi: oi for oi in personal}]
    for player in (2, 3, 4):
        mapping = {}
        for oi in personal:
            placed = next(i for i in f.instances if i.object_info == oi)
            copied = clone_active(
                m,
                f,
                oi,
                "MP Rainbow P%d %s" % (player, m.objs[oi].name),
                placed.x,
                placed.y,
            )
            next(i for i in f.instances if i.object_info == copied).layer = placed.layer
            mapping[oi] = copied
        mappings.append(mapping)
    # The physics anchors remain present during a personal death/respawn. A
    # camera attached to the hidden Chica body would briefly follow the host.
    m.minigame_avatars[26] = [mapping[vertical] for mapping in mappings]
    m.minigame_buttons[26] = [
        [mapping[oi], player - 1, bit]
        for player, mapping in enumerate(mappings, 1)
        if player > 1
        for oi, bit in ((1212, 4), (1213, 8), (1214, 4096))
    ]

    def fresh(g, mapping):
        g = clone(g)
        for c in g.conditions:
            if c.identifier:
                c.identifier = ids.take()
        for item in g.conditions + g.actions:
            remap_item(item, mapping)
        g.flags &= ~0x2000
        g.line = m.next_line()
        return g

    def guard(g, player, alive=False):
        if any(c.object_type == -1 and c.num == -42 for c in g.conditions):
            return
        branches, ornum = m.branches(g)
        conditions = []
        for branch in branches:
            if conditions:
                conditions.append(cond(ids, -1, ornum or -25, flags=0))
            conditions.extend(g.conditions[i] for i in branch)
            conditions.extend(
                [
                    c_gv(ids, G["players"], ">=", t_long(player)),
                    c_gv(ids, G["players"], ">", t_long(1)),
                    c_gv(ids, deaths, "<", t_long(33)),
                ]
            )
            if alive:
                conditions.append(
                    cond(
                        ids, 2, -24, mappings[player - 1][vertical], [p_expr(t_long(0))]
                    )
                )
        g.conditions = conditions

    def add(cs, actions):
        b.append(group(cs, actions, line=m.next_line()))

    # Keep solo death/retry verbatim. Co-op deaths stop only the affected runner;
    # the stage hazards and the other runners continue until the team exhausts
    # the original 33-attempt limit.
    for index in (65, 109):
        source[index].conditions.append(c_gv(ids, G["players"], "<=", t_long(1)))
    failure = source[98]
    check = next(
        c for c in failure.conditions if c.object_info == vertical and c.num == -42
    )
    check.object_type, check.object_info, check.object_info_list = -1, 0, 0
    check.num, check.params = -32, [p_global(deaths), p_cmp(">=", t_long(33))]
    # Solo keeps its stock death count; online/local co-op uses the shared pool.
    m.add_or_branch(
        ids,
        failure,
        failure.conditions.index(check),
        [
            cond(ids, 2, -42, vertical, [p_altval(0), p_cmp("=", t_long(33))]),
            c_gv(ids, G["players"], "<=", t_long(1)),
        ],
    )
    failure.flags |= 0x1400
    add([cond(ids, -3, -1, flags=0)], [a_set_gv(deaths, t_long(0))])
    # The stock failure line is a child of the solo death event. Co-op deaths
    # have separate parents, so evaluate the shared attempt limit at root level.
    add(
        [
            c_gv(ids, G["players"], ">", t_long(1)),
            c_gv(ids, deaths, ">=", t_long(33)),
            cond(ids, -1, -7),
        ],
        [clone(a) for a in source[98].actions],
    )

    for player, mapping in enumerate(mappings, 1):
        y, x, body = mapping[vertical], mapping[horizontal], mapping[actor]
        # Dedicated button flags drive the unchanged horizontal/jump/gravity
        # events. This also prevents a guest's input from steering P1.
        mask = (
            (t_gv(G["walk_mask"]),) if player == 1 else (t_gv(G["p%d_mask" % player]),)
        )
        if player > 1:
            add(
                [c_gv(ids, G["keyboard_p1"], "=", t_long(0))],
                [a_set_gv(G["p%d_mask" % player], t_long(1 << (player - 1)))],
            )
            add(
                [c_gv(ids, G["keyboard_p1"], "=", t_long(1))],
                [a_set_gv(G["p%d_mask" % player], t_long(1 << (player - 2)))],
            )
            # Clone complete parent/child physics trees, including boundary
            # records, so Fusion's selected-object lists remain well formed.
            for original in source[42:63]:
                copied = fresh(original, mapping)
                if not copied.flags & 0x8000:
                    guard(copied, player, alive=True)
                b.append(copied)
            follow = fresh(source[157], mapping)
            follow.actions = [
                a
                for a in follow.actions
                if a.object_type == 2 and a.object_info in mapping.values()
            ]
            guard(follow, player)
            b.append(follow)
        if player > 1:
            for button in (1212, 1213, 1214):
                add([cond(ids, -1, -1)], [act(2, 26, mapping[button])])
        # New participants start beside a current player; their own initialization
        # flag is reset when their seat is no longer occupied.
        if player > 1:
            add(
                [c_gv(ids, G["players"], "<", t_long(player))],
                [
                    act(2, 26, body),
                    act(2, 4, y),
                    act(2, 4, x),
                    act(2, 36, y, [p_expr(t_long(31))]),
                ],
            )
            add(
                [
                    c_gv(ids, G["players"], ">=", t_long(player)),
                    cond(ids, 2, -24, y, [p_expr(t_long(31))]),
                ],
                [
                    act(
                        2,
                        2,
                        y,
                        [
                            p_expr(
                                t_objexp(2, 11, vertical),
                                t_op("+"),
                                t_long((player - 1) * 22),
                            )
                        ],
                    ),
                    act(2, 3, y, [p_expr(t_objexp(2, 1, vertical))]),
                    act(2, 2, x, [p_expr(t_objexp(2, 11, y))]),
                    act(
                        2,
                        31,
                        y,
                        [
                            p_altval(1),
                            p_expr(t_objexp(2, 16, vertical, struct.pack("<h", 1))),
                        ],
                    ),
                    act(2, 35, y, [p_expr(t_long(31))]),
                    act(2, 27, body),
                ],
            )
        died = fresh(source[65], mapping)
        # Remove the solo-only guard added above.
        died.conditions = died.conditions[:-1]
        died.flags &= ~0x40
        died.actions = [
            a
            for a in died.actions
            if a.object_type == -2
            or a.object_type == -5
            or a.object_type == 2
            and a.object_info in mapping.values()
        ]
        died.actions.append(a_add_gv(deaths, t_long(1)))
        guard(died, player)
        b.append(died)
        retry = fresh(source[109], mapping)
        retry.conditions = retry.conditions[:-1]
        retry.actions = [
            a
            for a in retry.actions
            if a.object_type == -2
            or a.object_type == 2
            and a.object_info in mapping.values()
        ]
        guard(retry, player)
        b.append(retry)
        label = clone_text(m, f, "MP Rainbow player %d" % player, -400, -400, 40, 18)
        add(
            [
                c_gv(ids, G["players"], ">=", t_long(player)),
                c_gv(ids, G["players"], ">", t_long(1)),
                cond(ids, 2, -24, y, [p_expr(t_long(0))]),
            ],
            [
                act(3, 88, label, [p_expr(t_str("P%d" % player))]),
                act(
                    3, 2, label, [p_expr(t_objexp(2, 11, body), t_op("-"), t_long(10))]
                ),
                act(3, 3, label, [p_expr(t_objexp(2, 1, body), t_op("-"), t_long(54))]),
                act(3, 27, label),
            ],
        )
        add([c_gv(ids, G["players"], "<", t_long(player))], [act(3, 26, label)])
        add([c_gv(ids, G["players"], "<=", t_long(1))], [act(3, 26, label)])
        add([cond(ids, 2, -25, y, [p_expr(t_long(0))])], [act(3, 26, label)])

    # Any runner can reach a checkpoint, activate a trap or finish the course.
    # The original event still applies its stage-wide result exactly once.
    for index in (108, 112, 119, 120, 121, 125, 126, 127, 128, 131):
        g = source[index]
        trigger = next(
            (
                i
                for i, c in enumerate(g.conditions)
                if c.object_type == 2
                and (
                    c.object_info in (actor, vertical)
                    or m._objparam(c) in (actor, vertical)
                )
            ),
            None,
        )
        if trigger is None:
            raise RuntimeError("Rainbow shared trigger missing at event %d" % index)
        for player, mapping in enumerate(mappings[1:], 2):
            alternative = clone(g.conditions[trigger])
            alternative.identifier = ids.take()
            remap_item(alternative, mapping)
            m.add_or_branch(
                ids,
                g,
                trigger,
                [c_gv(ids, G["players"], ">=", t_long(player)), alternative],
            )
        g.flags |= 0x1400
    for mapping in mappings[1:]:
        checkpoint = next(
            a for a in source[108].actions if a.object_info == vertical and a.num == 31
        )
        copied = clone(checkpoint)
        remap_item(copied, mapping)
        source[108].actions.append(copied)
    m.sync_groups(f)
    m.log(
        "Rainbow co-op: separate runners, jumps, deaths and checkpoint respawns; shared course/result"
    )


def add_fighters(m):
    """Share Ultra's flight stage while giving each seat a ship and health."""
    f = m.frames[23]
    source = list(f.events.groups)
    if (
        len(source) != 423
        or not source[44].flags & 0x40
        or source[50].conditions[0].num != -42
        or not any(a.object_info == 1033 and a.num == 24 for a in source[145].actions)
    ):
        raise RuntimeError("Unrecognized Foxy Fighters stage events")
    m._companions(f)
    ids, G, b = Ids(f), m.G, m.blocks(f)[-1]
    seed = G["fighters_health"] = m.alloc_global("mp_fighters_start_health")
    actor, hitbox, health, fire = 1037, 87, 1033, 1074
    personal = (1060, 1046, health, fire)
    mappings = [{oi: oi for oi in (actor, hitbox, *personal)}]
    for player in (2, 3, 4):
        mapping = {
            actor: m.oi("mp walker %d" % player, f),
            hitbox: m.oi("mp hitbox %d" % player, f),
        }
        for oi in personal:
            placed = next(i for i in f.instances if i.object_info == oi)
            copied = clone_active(
                m,
                f,
                oi,
                "MP Fighters P%d %s" % (player, m.objs[oi].name),
                placed.x,
                placed.y,
            )
            next(i for i in f.instances if i.object_info == copied).layer = placed.layer
            mapping[oi] = copied
        mappings.append(mapping)
    m.minigame_buttons[23] = [
        [mapping[fire], p - 1, 16384] for p, mapping in enumerate(mappings, 1) if p > 1
    ]

    def add(cs, actions):
        b.append(group(cs, actions, line=m.next_line()))

    def alive(mapping):
        return c_compare(ids, (t_objexp(7, 80, mapping[health]),), ">", (t_long(0),))

    def ready(player, mapping):
        return [
            c_gv(ids, G["players"], ">=", t_long(player)),
            c_compare(ids, (t_objexp(2, 15, 394),), ">", (t_long(0),)),
            c_compare(ids, (t_objexp(2, 15, actor),), ">", (t_long(0),)),
            cond(ids, 2, -42, actor, [p_altval(0), p_cmp(">=", t_long(1))]),
            cond(ids, 2, -42, actor, [p_altval(0), p_cmp("<", t_long(19))]),
            alive(mapping),
        ]

    def fresh(original, mapping):
        copied = clone(original)
        for c in copied.conditions:
            if c.identifier:
                c.identifier = ids.take()
        for item in copied.conditions + copied.actions:
            remap_item(item, mapping)
        copied.flags &= ~0x2000
        copied.line = m.next_line()
        return copied

    # These are new independent root events; the original stage's activated
    # groups still own waves, bosses, dialogue, scoring and the shared result.
    add([cond(ids, -3, -1, flags=0)], [a_set_gv(seed, t_objexp(7, 80, health))])
    for player, mapping in enumerate(mappings[1:], 2):
        ship, collider, hp = mapping[actor], mapping[hitbox], mapping[health]
        # Constrain the generic flight walker to living, connected participants
        # after the source ready sequence. Do not respawn a defeated occupant.
        active = G["p%d_active" % player]
        for g in b:
            if any(
                a.object_type == -1
                and a.num in (3, 27)
                and a.params
                and struct.unpack_from("<h", a.params[0].data)[0] == active
                and t_long(1) in a.params[1].data
                for a in g.actions
            ):
                g.conditions.extend(ready(player, mapping))
            if any(
                a.object_info == collider
                and a.num == 35
                and a.params
                and t_long(31) in a.params[0].data
                for a in g.actions
            ):
                offset = (-100, 100, 180)[player - 2]
                g.actions.append(
                    act(
                        2,
                        3,
                        collider,
                        [
                            p_expr(
                                t_func(F_MAX),
                                t_long(60),
                                t_comma(),
                                t_func(F_MIN),
                                t_long(420),
                                t_comma(),
                                t_objexp(2, 1, hitbox),
                                t_op("+"),
                                t_long(offset),
                                t_close(),
                                t_close(),
                            )
                        ],
                    )
                )
        add([cond(ids, -3, -1, flags=0)], [act(7, 80, hp, [p_expr(t_gv(seed))])])
        add(
            [c_gv(ids, G["players"], "<", t_long(player))],
            [act(7, 80, hp, [p_expr(t_gv(seed))])],
        )
        add([cond(ids, -1, -1)], [act(2, 26, mapping[fire]), act(7, 26, hp)])
        add(
            ready(player, mapping) + [cond(ids, 2, -13, collider)],
            [act(2, 9, collider)],
        )
        # Team power-ups and story phase are shared; weapon cooldowns, hurt
        # flashes and health remain personal.
        add(
            [cond(ids, -1, -1)],
            [
                act(2, 31, ship, [p_altval(n), p_expr(t_altval(2, actor, n))])
                for n in (0, 1, 3)
            ],
        )
        for index in (25, 26, 27):
            copied = fresh(source[index], mapping)
            copied.conditions.extend(ready(player, mapping))
            b.append(copied)
        for index in range(44, 51):
            copied = fresh(source[index], mapping)
            if index == 44:
                copied.flags &= ~0x8000
                copied.conditions = [
                    c
                    for c in copied.conditions
                    if not (c.object_type == -1 and c.num == -43)
                ]
                guard_conditions(m, ids, copied, ready(player, mapping))
            b.append(copied)
        for index in (137, 138, 139, 140, 141, 143, 144):
            copied = fresh(source[index], {**mapping, 32773: ship})
            copied.conditions.extend(ready(player, mapping))
            b.append(copied)
        # A guest can collect the same shared weapon upgrade. Apply the source
        # actions to the source power state, then distribute it on the next tick.
        pickup = clone(source[189])
        for c in pickup.conditions:
            c.identifier = ids.take()
            remap_item(c, mapping)
        pickup.flags &= ~0x2000
        pickup.conditions.extend(ready(player, mapping))
        pickup.line = m.next_line()
        b.append(pickup)

    # Empty/dead seats do not fire or absorb hazards. Losing P1 does not end the
    # run while another connected ship is alive.
    for index in (44, 137, 138, 139, 140, 141, 189):
        source[index].conditions.append(alive(mappings[0]))
    remaining = []
    for player, mapping in enumerate(mappings[1:], 2):
        if remaining:
            remaining.append(t_op("+"))
        remaining.extend(
            (
                t_func(F_MAX),
                t_long(0),
                t_comma(),
                t_func(F_MIN),
                t_long(1),
                t_comma(),
                t_gv(G["players"]),
                t_op("-"),
                t_long(player - 1),
                t_close(),
                t_close(),
                t_op("*"),
                t_func(F_MAX),
                t_long(0),
                t_comma(),
                t_objexp(7, 80, mapping[health]),
                t_close(),
            )
        )
    source[145].conditions.append(c_compare(ids, tuple(remaining), "<=", (t_long(0),)))
    add(
        [
            c_compare(ids, (t_objexp(7, 80, health),), "<=", (t_long(0),)),
            c_gv(ids, G["players"], ">", t_long(1)),
        ],
        [act(2, 4, hitbox), act(2, 26, actor), act(2, 36, fire, [p_expr(t_long(0))])],
    )
    for player, mapping in enumerate(mappings, 1):
        label = clone_text(m, f, "MP Fighters player %d" % player, -400, -400, 112, 20)
        add(
            ready(player, mapping) + [c_gv(ids, G["players"], ">", t_long(1))],
            [
                act(
                    3,
                    88,
                    label,
                    [
                        p_expr(
                            t_str("P%d HP " % player),
                            t_op("+"),
                            t_func(F_TOSTRING),
                            t_objexp(7, 80, mapping[health]),
                            t_close(),
                        )
                    ],
                ),
                act(
                    3,
                    2,
                    label,
                    [p_expr(t_objexp(2, 11, mapping[actor]), t_op("-"), t_long(38))],
                ),
                act(
                    3,
                    3,
                    label,
                    [p_expr(t_objexp(2, 1, mapping[actor]), t_op("-"), t_long(46))],
                ),
                act(3, 27, label),
            ],
        )
        add(
            [c_compare(ids, (t_objexp(7, 80, mapping[health]),), "<=", (t_long(0),))],
            [act(3, 26, label)],
        )
        add([c_gv(ids, G["players"], "<", t_long(player))], [act(3, 26, label)])
        add([c_gv(ids, G["players"], "<=", t_long(1))], [act(3, 26, label)])
        add(
            [cond(ids, 2, -42, actor, [p_altval(0), p_cmp(">=", t_long(19))])],
            [act(3, 26, label)],
        )
    m.sync_groups(f)
    m.log(
        "Foxy Fighters co-op: personal ships, fire, health and damage; shared waves, upgrades and result"
    )


def add_fishing(m):
    f = m.frames[14]
    source = list(f.events.groups)
    if len(source) != 122 or source[32].conditions[0].num != -42:
        raise RuntimeError("Unrecognized fishing stage events")
    ids, G, b = Ids(f), m.G, m.blocks(f)[-1]
    mappings = clone_participants(m, f, (960, 961, 963, 970, 971, 972), "MP Fishing")
    m.minigame_buttons[14] = [
        [mapping[oi], p - 1, bit]
        for p, mapping in enumerate(mappings, 1)
        for oi, bit in ((970, 4), (971, 8), (972, 4096))
    ]
    finished = G["fishing_finished"] = m.alloc_global("mp_fishing_finished")
    coop = lambda: c_gv(ids, G["players"], ">", t_long(1))

    def add(cs, actions):
        b.append(group(cs, actions, line=m.next_line()))

    def active(player):
        return [
            coop(),
            c_gv(ids, G["players"], ">=", t_long(player)),
            c_gv(ids, finished, "=", t_long(0)),
        ]

    add([cond(ids, -3, -1, flags=0)], [a_set_gv(finished, t_long(0))])
    # One timer runs for the whole group even after P1 has caught a fish.
    source[28].conditions.append(c_gv(ids, G["players"], "<=", t_long(1)))
    add(
        active(1) + [clone(source[28].conditions[0]), clone(source[28].conditions[1])],
        [clone(a) for a in source[28].actions],
    )
    source[38].conditions.append(c_gv(ids, G["players"], "<=", t_long(1)))
    # A caught fish is consumed once even when several hooks arrive together.
    # The stock score starts at zero, so adding also preserves a solo catch.
    next(a for a in source[34].actions if a.object_info == 964 and a.num == 80).num = 81
    source[34].actions.append(act(2, 24, 967))
    for player, mapping in enumerate(mappings, 1):
        body, hook = mapping[960], mapping[961]
        if player > 1:
            # Complete selected-object tree, excluding the one shared timer.
            for index in (27, 29, 30, 31, 32, 33, 34, 35, 36, 43):
                copied = participant_copy(m, ids, source[index], mapping)
                if not copied.flags & 0x8000:
                    copied.conditions.extend(active(player))
                    if index in (33, 34):
                        copied.conditions.append(
                            cond(ids, 2, -24, body, [p_expr(t_long(0))])
                        )
                if index == 43:
                    copied.actions = [
                        a for a in copied.actions if a.object_info in mapping.values()
                    ]
                b.append(copied)
            add(
                [cond(ids, -3, -1, flags=0)],
                [
                    act(2, 2, hook, [p_expr(t_long(110 + (player - 1) * 180))]),
                    act(2, 4, hook),
                ],
            )
        else:
            for index in (33, 34):
                source[index].conditions.append(
                    cond(ids, 2, -24, body, [p_expr(t_long(0))])
                )
        drop = participant_copy(m, ids, source[15], mapping)
        drop.conditions = active(player) + [
            cond(ids, 2, -24, body, [p_expr(t_long(0))]),
            cond(ids, 2, -24, hook, [p_expr(t_long(0))]),
            cond(ids, 2, -25, mapping[972], [p_expr(t_long(1))]),
        ]
        b.append(drop)
        if player > 1:
            add(
                [c_gv(ids, G["players"], "<", t_long(player))],
                [act(2, 26, body), act(2, 26, hook), act(2, 4, hook)],
            )
        add([coop()], [act(2, 26, mapping[oi]) for oi in (970, 971, 972)])
        label = clone_text(m, f, "MP Fishing player %d" % player, -400, -400, 110, 20)
        add(
            active(player),
            [
                act(3, 88, label, [p_expr(t_str("P%d  A: drop" % player))]),
                act(
                    3, 2, label, [p_expr(t_objexp(2, 11, hook), t_op("-"), t_long(36))]
                ),
                act(3, 3, label, [p_expr(t_long(58 + (player - 1) * 18))]),
                act(3, 27, label),
            ],
        )
        add(
            active(player) + [cond(ids, 2, -25, body, [p_expr(t_long(0))])],
            [act(3, 88, label, [p_expr(t_str("P%d  done" % player))])],
        )
        add([c_gv(ids, G["players"], "<", t_long(player))], [act(3, 26, label)])
        add([c_gv(ids, G["players"], "<=", t_long(1))], [act(3, 26, label)])
        add([c_gv(ids, finished, "=", t_long(1))], [act(3, 26, label)])
    # One source return timer after all occupied hooks have resolved. Catch
    # events remain authoritative and retain the source fish/currency rules.
    all_done = active(1)
    for player, mapping in enumerate(mappings, 1):
        all_done.append(c_compare(ids, (t_gv(G["players"]),), "<", (t_long(player),)))
        # Absent seat OR finished hook. AND these pairs at root level.
        if player == 1:
            all_done.pop()
            all_done.append(cond(ids, 2, -25, mapping[960], [p_expr(t_long(0))]))
        else:
            # Use a numeric flag expression, so OR cannot reset earlier SOLs.
            all_done[-1] = c_compare(
                ids,
                (
                    t_func(F_MAX),
                    t_long(0),
                    t_comma(),
                    t_func(F_MIN),
                    t_long(1),
                    t_comma(),
                    t_gv(G["players"]),
                    t_op("-"),
                    t_long(player - 1),
                    t_close(),
                    t_close(),
                    t_op("*"),
                    t_objexp(2, 13, mapping[960]),
                    t_long(0),
                    t_close(),
                ),
                "=",
                (
                    t_func(F_MAX),
                    t_long(0),
                    t_comma(),
                    t_func(F_MIN),
                    t_long(1),
                    t_comma(),
                    t_gv(G["players"]),
                    t_op("-"),
                    t_long(player - 1),
                    t_close(),
                    t_close(),
                ),
            )
    ending = [clone(a) for a in source[38].actions]
    for mapping in mappings[1:]:
        for a in source[38].actions:
            if a.object_info in (961, 963):
                copied = clone(a)
                remap_item(copied, mapping)
                ending.append(copied)
    ending.append(a_set_gv(finished, t_long(1)))
    add(all_done, ending)
    add(
        active(1) + [clone(source[37].conditions[0])],
        [act(2, 35, mapping[960], [p_expr(t_long(0))]) for mapping in mappings],
    )
    m.sync_groups(f)
    m.log(
        "Fishing co-op: separate hooks and drops; contested fish resolve on host; shared timer and return"
    )


def add_space(m):
    f = m.frames[24]
    source = list(f.events.groups)
    if (
        len(source) != 286
        or source[95].conditions[0].num != -42
        or source[101].conditions[0].num != -42
    ):
        raise RuntimeError("Unrecognized FNaF 57 stage events")
    ids, G, b = Ids(f), m.G, m.blocks(f)[-1]
    body, vertical, horizontal, collision, hp = 1124, 1125, 1161, 1162, 1108
    buttons = ((1148, 16384), (1149, 4096), (1150, 4), (1151, 8), (1152, 2))
    personal = (
        body,
        vertical,
        horizontal,
        collision,
        hp,
        1100,
        *(oi for oi, _ in buttons),
    )
    mappings = clone_participants(m, f, personal, "MP Space")
    m.minigame_avatars[24] = [mapping[vertical] for mapping in mappings]
    m.minigame_buttons[24] = [
        [mapping[oi], p - 1, bit]
        for p, mapping in enumerate(mappings, 1)
        if p > 1
        for oi, bit in buttons
    ]
    started = G["space_started"] = m.alloc_global("mp_space_started")
    seed = G["space_health"] = m.alloc_global("mp_space_start_health")
    for index in (15, 16):
        source[index].actions.append(a_set_gv(started, t_long(1)))

    def add(cs, actions):
        b.append(group(cs, actions, line=m.next_line()))

    def alive(mapping):
        return c_compare(ids, (t_objexp(7, 80, mapping[hp]),), ">", (t_long(0),))

    def ready(player, mapping):
        return [
            c_gv(ids, G["players"], ">=", t_long(player)),
            c_gv(ids, started, "=", t_long(1)),
            c_compare(ids, (t_objexp(2, 15, vertical),), ">", (t_long(0),)),
            alive(mapping),
        ]

    add(
        [cond(ids, -3, -1, flags=0)],
        [a_set_gv(started, t_long(0)), a_set_gv(seed, t_objexp(7, 80, hp))],
    )
    for player, mapping in enumerate(mappings[1:], 2):
        y, x, actor, health = [mapping[oi] for oi in (vertical, horizontal, body, hp)]
        add([cond(ids, -3, -1, flags=0)], [act(7, 80, health, [p_expr(t_gv(seed))])])
        add(
            [c_gv(ids, G["players"], "<", t_long(player))],
            [
                act(7, 80, health, [p_expr(t_gv(seed))]),
                act(2, 36, y, [p_expr(t_long(31))]),
            ],
        )
        add(
            ready(player, mapping) + [cond(ids, 2, -24, y, [p_expr(t_long(31))])],
            [
                act(
                    2,
                    2,
                    y,
                    [
                        p_expr(
                            t_objexp(2, 11, vertical),
                            t_op("+"),
                            t_long((player - 1) * 24),
                        )
                    ],
                ),
                act(2, 2, x, [p_expr(t_objexp(2, 11, y))]),
                act(2, 3, y, [p_expr(t_objexp(2, 1, vertical))]),
                act(2, 35, y, [p_expr(t_long(31))]),
            ],
        )
        # Preserve complete nested physics/weapon/hurt trees. Only the shared
        # bullet lifetime event (96) remains singular.
        for index in [*range(60, 96), *range(97, 102), 103, 105, 181]:
            copied = participant_copy(m, ids, source[index], mapping)
            if not copied.flags & 0x8000:
                guard_conditions(m, ids, copied, ready(player, mapping))
            b.append(copied)
        for index in (197, 198):
            copied = participant_copy(m, ids, source[index], mapping)
            copied.actions = [
                a
                for a in copied.actions
                if a.object_type == 2 and a.object_info in mapping.values()
            ]
            copied.conditions.extend(ready(player, mapping))
            b.append(copied)
        # Weapon pickups are team upgrades. A guest's accepted pickup runs the
        # source action once; all weapons use the same level/damage afterwards.
        pickup = clone(source[106])
        for c in pickup.conditions:
            c.identifier = ids.take()
            remap_item(c, mapping)
        pickup.flags &= ~0x2000
        pickup.line = m.next_line()
        pickup.conditions.extend(ready(player, mapping))
        b.append(pickup)
        add(
            [cond(ids, -1, -1)],
            [act(2, 31, y, [p_altval(2), p_expr(t_altval(2, vertical, 2))])]
            + [act(2, 26, mapping[oi]) for oi, _ in buttons]
            + [act(7, 26, health), act(2, 26, mapping[1100])],
        )
        add(
            [c_gv(ids, G["players"], "<", t_long(player))],
            [act(2, 26, actor), act(2, 4, x), act(2, 4, y)],
        )
        add(
            [c_compare(ids, (t_objexp(7, 80, health),), "<=", (t_long(0),))],
            [act(2, 26, actor), act(2, 4, x), act(2, 4, y)],
        )
        add(
            [c_gv(ids, started, "=", t_long(0))],
            [act(2, 26, actor), act(2, 4, x), act(2, 4, y)],
        )
        add(ready(player, mapping), [act(2, 27, actor)])
    # Keep P1's body/physics allocated when only P1 has fallen; the source stage
    # still uses its checkpoint/cutscene state until the last living seat falls.
    for index in range(60, 102):
        g = source[index]
        if not g.flags & 0x8000 and index != 96:
            guard_conditions(m, ids, g, [alive(mappings[0])])
    remaining = []
    for player, mapping in enumerate(mappings[1:], 2):
        if remaining:
            remaining.append(t_op("+"))
        remaining.extend(
            (
                t_func(F_MAX),
                t_long(0),
                t_comma(),
                t_func(F_MIN),
                t_long(1),
                t_comma(),
                t_gv(G["players"]),
                t_op("-"),
                t_long(player - 1),
                t_close(),
                t_close(),
                t_op("*"),
                t_func(F_MAX),
                t_long(0),
                t_comma(),
                t_objexp(7, 80, mapping[hp]),
                t_close(),
            )
        )
    source[5].conditions.append(c_compare(ids, tuple(remaining), "<=", (t_long(0),)))
    add(
        [
            c_compare(ids, (t_objexp(7, 80, hp),), "<=", (t_long(0),)),
            c_gv(ids, G["players"], ">", t_long(1)),
        ],
        [act(2, 26, body), act(2, 4, vertical), act(2, 4, horizontal)],
    )
    # Teleporting into Ultra's next area is a shared checkpoint. Each guest can
    # trigger it; keep the single world/AI action list and move all owned actors.
    teleport = source[104]
    trigger = next(
        i for i, c in enumerate(teleport.conditions) if c.object_info == collision
    )
    for player, mapping in enumerate(mappings[1:], 2):
        c = clone(teleport.conditions[trigger])
        c.identifier = ids.take()
        remap_item(c, mapping)
        m.add_or_branch(ids, teleport, trigger, [*ready(player, mapping), c])
        for a in list(source[104].actions):
            if a.object_info in (vertical, horizontal):
                copied = clone(a)
                remap_item(copied, mapping)
                teleport.actions.append(copied)
        teleport.actions += [act(7, 80, mapping[hp], [p_expr(t_gv(seed))])]
    teleport.flags |= 0x1400
    for player, mapping in enumerate(mappings, 1):
        label = clone_text(m, f, "MP Space player %d" % player, -400, -400, 110, 20)
        add(
            ready(player, mapping) + [c_gv(ids, G["players"], ">", t_long(1))],
            [
                act(
                    3,
                    88,
                    label,
                    [
                        p_expr(
                            t_str("P%d HP " % player),
                            t_op("+"),
                            t_func(F_TOSTRING),
                            t_objexp(7, 80, mapping[hp]),
                            t_close(),
                        )
                    ],
                ),
                act(
                    3,
                    2,
                    label,
                    [p_expr(t_objexp(2, 11, mapping[body]), t_op("-"), t_long(28))],
                ),
                act(
                    3,
                    3,
                    label,
                    [p_expr(t_objexp(2, 1, mapping[body]), t_op("-"), t_long(90))],
                ),
                act(3, 27, label),
            ],
        )
        for cs in (
            [c_gv(ids, G["players"], "<", t_long(player))],
            [c_gv(ids, started, "=", t_long(0))],
            [c_compare(ids, (t_objexp(7, 80, mapping[hp]),), "<=", (t_long(0),))],
            [c_compare(ids, (t_objexp(2, 15, vertical),), "=", (t_long(0),))],
        ):
            add(cs, [act(3, 26, label)])
    m.sync_groups(f)
    m.log(
        "FNaF 57 co-op: separate movement, jump, crouch, weapons and health; shared upgrades, checkpoint and result"
    )


def add_foxy_trial(m):
    f = m.frames[25]
    source = list(f.events.groups)
    if (
        len(source) != 164
        or source[41].conditions[0].num != -42
        or source[59].conditions[0].num != -42
    ):
        raise RuntimeError("Unrecognized Foxy.exe trial events")
    ids, G, b = Ids(f), m.G, m.blocks(f)[-1]
    body, collider, enemy = 1164, 1176, 1167
    mappings = clone_participants(
        m, f, (body, collider, enemy, 1173, 1150, 1172), "MP Trial"
    )
    m.minigame_avatars[25] = [mapping[body] for mapping in mappings]
    m.minigame_buttons[25] = [
        [mapping[oi], p - 1, bit]
        for p, mapping in enumerate(mappings, 1)
        if p > 1
        for oi, bit in ((1150, 4), (1172, 8))
    ]
    started = G["trial_started"] = m.alloc_global("mp_trial_started")
    finish = G["trial_finish"] = m.alloc_global("mp_trial_finish_request")
    source[10].actions.append(a_set_gv(started, t_long(1)))

    def add(cs, actions):
        b.append(group(cs, actions, line=m.next_line()))

    def alive(mapping):
        return cond(ids, 2, -42, mapping[body], [p_altval(0), p_cmp(">", t_long(0))])

    def ready(player, mapping):
        return [
            c_gv(ids, G["players"], ">=", t_long(player)),
            c_gv(ids, started, "=", t_long(1)),
            cond(ids, 2, -42, body, [p_altval(1), p_cmp("<", t_long(4))]),
            alive(mapping),
        ]

    add(
        [cond(ids, -3, -1, flags=0)],
        [a_set_gv(started, t_long(0)), a_set_gv(finish, t_long(0))],
    )
    for player, mapping in enumerate(mappings[1:], 2):
        actor = mapping[body]
        add(
            ready(player, mapping) + [cond(ids, 2, -24, actor, [p_expr(t_long(31))])],
            [
                act(
                    2,
                    2,
                    actor,
                    [
                        p_expr(
                            t_objexp(2, 11, body), t_op("+"), t_long((player - 1) * 28)
                        )
                    ],
                ),
                act(2, 3, actor, [p_expr(t_objexp(2, 1, body))]),
                act(2, 35, actor, [p_expr(t_long(31))]),
            ],
        )
        add(
            [c_gv(ids, G["players"], "<", t_long(player))],
            [
                act(2, 36, actor, [p_expr(t_long(31))]),
                act(2, 31, actor, [p_altval(0), p_expr(t_long(3))]),
            ],
        )
        for index in range(30, 60):
            copied = participant_copy(m, ids, source[index], mapping)
            if not copied.flags & 0x8000:
                copied.conditions.extend(ready(player, mapping))
            # The stage's background, music and perspective remain shared. The
            # personal selected-object trees own movement and hazard contacts.
            copied.actions = [
                a
                for a in copied.actions
                if a.object_info not in (1166, 1168) or a.object_type < 0
            ]
            if index == 40:
                copied.actions = [a_set_gv(finish, t_long(1))]
            if not copied.actions:
                copied.actions = [act(-1, 0)]
            b.append(copied)
        follow = participant_copy(m, ids, source[84], mapping)
        follow.actions = [
            a
            for a in follow.actions
            if a.object_type == 2 and a.object_info in mapping.values()
        ]
        follow.conditions.extend(ready(player, mapping))
        b.append(follow)
        # Personal pursuers still fade after passing the edge of the trial.
        for index in (76, 77):
            copied = participant_copy(m, ids, source[index], mapping)
            copied.conditions.extend(ready(player, mapping))
            b.append(copied)
        add([cond(ids, -1, -1)], [act(2, 26, mapping[oi]) for oi in (1150, 1172, 1173)])
        for cs in (
            [c_gv(ids, G["players"], "<", t_long(player))],
            [c_gv(ids, started, "=", t_long(0))],
            [cond(ids, 2, -42, actor, [p_altval(0), p_cmp("<=", t_long(0))])],
            [cond(ids, 2, -42, body, [p_altval(1), p_cmp(">=", t_long(4))])],
        ):
            add(cs, [act(2, 26, actor), act(2, 4, actor), act(2, 26, mapping[enemy])])
        add(ready(player, mapping), [act(2, 27, actor)])
    # The first valid arrival advances the shared trial exactly once. Everyone
    # enters the next lane together; other players retain their own lives.
    g = source[40]
    trigger = next(
        i for i, c in enumerate(g.conditions) if c.object_info == body and c.num == -17
    )
    m.add_or_branch(ids, g, trigger, [c_gv(ids, finish, "=", t_long(1))])
    g.flags |= 0x1400
    g.actions += [act(2, 2, body, [p_expr(t_long(240))]), a_set_gv(finish, t_long(0))]
    for mapping in mappings[1:]:
        g.actions += [
            act(2, 2, mapping[body], [p_expr(t_long(240))]),
            act(2, 3, mapping[body], [p_expr(t_objexp(2, 1, body))]),
            act(2, 31, mapping[body], [p_altval(1), p_expr(t_altval(2, body, 1))]),
        ]
    for index in (30, 33, 36, 46, 47, 48, 50, 55, 56):
        if source[index].conditions[0].num != -42:
            source[index].conditions.append(alive(mappings[0]))
    # Preserve the single source success/reward and failure/return sequences.
    for player, mapping in enumerate(mappings[1:], 2):
        present = (
            t_func(F_MAX),
            t_long(0),
            t_comma(),
            t_func(F_MIN),
            t_long(1),
            t_comma(),
            t_gv(G["players"]),
            t_op("-"),
            t_long(player - 1),
            t_close(),
            t_close(),
        )
        source[83].conditions.append(
            c_compare(
                ids,
                (*present, t_op("*"), t_altval(2, mapping[body], 0)),
                "<=",
                (t_long(0),),
            )
        )
    add(
        [
            cond(ids, 2, -42, body, [p_altval(0), p_cmp("<=", t_long(0))]),
            c_gv(ids, G["players"], ">", t_long(1)),
        ],
        [act(2, 26, body), act(2, 4, body)],
    )
    for player, mapping in enumerate(mappings, 1):
        label = clone_text(m, f, "MP Trial player %d" % player, -400, -400, 110, 20)
        add(
            ready(player, mapping) + [c_gv(ids, G["players"], ">", t_long(1))],
            [
                act(
                    3,
                    88,
                    label,
                    [
                        p_expr(
                            t_str("P%d lives " % player),
                            t_op("+"),
                            t_func(F_TOSTRING),
                            t_altval(2, mapping[body], 0),
                            t_close(),
                        )
                    ],
                ),
                act(
                    3,
                    2,
                    label,
                    [p_expr(t_objexp(2, 11, mapping[body]), t_op("-"), t_long(30))],
                ),
                act(
                    3,
                    3,
                    label,
                    [p_expr(t_objexp(2, 1, mapping[body]), t_op("-"), t_long(75))],
                ),
                act(3, 27, label),
            ],
        )
        for cs in (
            [c_gv(ids, G["players"], "<", t_long(player))],
            [c_gv(ids, started, "=", t_long(0))],
            [cond(ids, 2, -42, mapping[body], [p_altval(0), p_cmp("<=", t_long(0))])],
            [cond(ids, 2, -42, body, [p_altval(1), p_cmp(">=", t_long(4))])],
        ):
            add(cs, [act(3, 26, label)])
    m.sync_groups(f)
    m.log(
        "Foxy.exe co-op: personal movement, lives and pursuers; shared trial advances and one outcome"
    )
