"""Shared co-op party drafting, using Ultra's own portraits and slot save data."""
import struct

from .evb import (F_TOSTRING, Ids, act, a_add_gv, a_set_gv, c_compare, c_gv, clone,
                  cond, expr, group, p_altval, p_cmp, p_expr, t_altval, t_close,
                  t_comma, t_double, t_ext, t_func, t_gv, t_long, t_objexp, t_op, t_str)
from .fusion import ObjectDef, Param


def clone_text(m, f, name, x, y, width, height, source=57):
    base = m.objs[source]
    o = ObjectDef(len(m.objs))
    header = bytearray(base.header)
    struct.pack_into("<h", header, 0, o.index)
    o.header, o.name, o.shader = bytes(header), name, b"\0\0\0\0"
    props = bytearray(base.props)
    props[20:36] = struct.pack("<8h", *([-1] * 8))
    data_offset = struct.unpack_from("<H", props, 36)[0]
    if data_offset < 70 or data_offset + 16 > len(props):
        raise RuntimeError("Unexpected String layout while creating co-op labels")
    struct.pack_into("<ii", props, data_offset + 4, width, height)
    paragraphs = struct.unpack_from("<I", props, data_offset + 12)[0]
    for index in range(paragraphs):
        offset = data_offset + struct.unpack_from("<I", props, data_offset + 16 + index * 4)[0]
        struct.pack_into("<I", props, offset + 4, 0xffffff)
    o.props = bytes(props)
    m.objs.append(o)
    m.ensure_instance(f, o.index)
    instance = next(i for i in f.instances if i.object_info == o.index)
    instance.x, instance.y = x, y
    instance.layer = next((i.layer for i in f.instances if i.object_info == source),
                          max((i.layer for i in f.instances if m.objs[i.object_info].type == 3), default=0))
    return o.index


def clone_active(m, f, source, name, x, y):
    base = m.objs[source]
    o = ObjectDef(len(m.objs))
    o.header = struct.pack("<h", o.index) + base.header[2:]
    o.name, o.shader = name, b"\0\0\0\0"
    props = bytearray(base.props)
    props[20:36] = struct.pack("<8h", *([-1] * 8))
    o.props = bytes(props)
    m.objs.append(o)
    m.ensure_instance(f, o.index)
    instance = next(i for i in f.instances if i.object_info == o.index)
    instance.x, instance.y = x, y
    instance.layer = max((i.layer for i in f.instances if m.objs[i.object_info].type == 3), default=0)
    return o.index


def add_party(m, otype, online):
    f = m.frames[3]
    b = m.blocks(f)[0]
    ids = Ids(f)
    icon, available = m.oi("spr character icon", f), m.oi("spr available", f)
    done, reset = m.oi("btt done", f), m.oi("btt reset", f)
    category = m.oi("Background fnaf game (1)", f)
    previous, following = m.oi("btt return 2", f), m.oi("btt return 3", f)
    slot = m.G["party_slot"] = m.alloc_global("mp_party_slot")
    accepted = m.G["party_done"] = m.alloc_global("mp_party_done")
    G = m.G
    native = lambda n, *args: (t_ext(otype, n, online), *args, *((t_close(),) if args else ()))
    coop = lambda: c_compare(ids, (t_gv(G["players"]), t_op("+"), t_gv(G["online_session"])), ">", (t_long(1),))
    solo = lambda: c_compare(ids, (t_gv(G["players"]), t_op("+"), t_gv(G["online_session"])), "<=", (t_long(1),))
    add = lambda cs, actions: group(cs, actions, line=m.next_line())

    # Keep initialization, the Done event's child tree, Back and the slot save
    # callback. The mouse-only stock selector enforces unique characters and
    # silently chooses the next slot, so it is inactive during a co-op draft.
    original = list(b)
    done_event = next(g for g in original if any(c.object_type >= 32 and c.num == -87 and
                      m._objparam(c) == done for c in g.conditions))
    back = m.oi("btt return", f)
    back_event = next(g for g in original if any(c.object_type >= 32 and c.num == -87 and
                      m._objparam(c) == back for c in g.conditions))
    done_index = original.index(done_event)
    done_end = done_index + 1
    while done_end < len(original) and original[done_end].flags & 0x8000:
        done_end += 1
    for index, g in enumerate(original):
        if index < 14 or done_index <= index < done_end:
            continue
        if any(c.object_type == -1 and c.num in (-10, -11, -42) for c in g.conditions):
            continue
        if any(a.object_info == category and a.object_type == 2 and a.num == 40 for a in g.actions):
            continue  # Ultra's own category header artwork and ordering
        if any(c.object_info == available and c.num == -41 and c.params and
               "save".encode("utf-16-le") in c.params[0].data for c in g.conditions):
            continue
        if any(c.object_type >= 32 and c.num == -87 and m._objparam(c) == m.oi("btt return", f)
               for c in g.conditions):
            continue
        branches, ornum = m.branches(g)
        out = []
        for indices in branches:
            if out:
                out.append(cond(ids, -1, ornum or -25, flags=0))
            out.extend(g.conditions[i] for i in indices)
            out.append(solo())
        g.conditions = out
    done_event.conditions.append(solo())
    done_event.conditions += [cond(ids, -1, -25, flags=0), c_gv(ids, accepted, "=", t_long(1)), coop()]
    done_event.flags |= 0x1400  # logical OR, retaining the original child event tree

    top = [add([cond(ids, -3, -1, flags=0)], [a_set_gv(slot, t_long(1)), a_set_gv(accepted, t_long(0))]),
           add([cond(ids, -1, -1)], [a_set_gv(G["pads"], t_long(0))])]
    for pad in range(4):
        top.append(add([m.pad_cond(ids, 0, (t_long(pad),))], [a_add_gv(G["pads"], t_long(1))]))
    top += [
        add([cond(ids, -1, -1)], [a_set_gv(G["players"], t_gv(G["pads"]), t_op("+"), t_gv(G["keyboard_p1"]))]),
        add([c_gv(ids, G["players"], "<", t_long(1))], [a_set_gv(G["players"], t_long(1))]),
        add([coop()], [a_set_gv(G["turn_slot"], t_gv(slot), t_op("-"), t_long(1), t_op("mod"), t_long(4), t_op("+"), t_long(1))] + m.turn_owner_actions()),
    ]
    b[0:0] = top

    def label(name, x, y, width, height, source=57):
        return clone_text(m, f, name, x, y, width, height, source)

    extras = []
    title_a = label("MP party team A", 632, 18, 148, 22, 70)
    title_b = label("MP party reserves", 632, 190, 148, 22, 70)
    prompt = label("MP party instructions", 20, 412, 580, 60, 241)
    preview = label("MP party character details", 20, 384, 580, 24)
    cursor = label("MP party cursor", 20, 20, 28, 22, 70)
    pages = label("MP party pages", 20, 354, 480, 24, 70)
    title = label("MP party title", 220, 24, 396, 24, 70)
    skin = label("MP party skin", 340, 386, 270, 22, 70)
    labels = [title_a, title_b, prompt, preview, cursor, pages, title, skin]
    text = lambda oi, tokens: act(3, 88, oi, [Param(45, expr(*tokens))])
    show = lambda oi: act(3, 27, oi)
    color = lambda oi, rgb: act(3, 83, oi, [p_expr(t_long(rgb))])
    extras.append(add([coop()], [act(3, 26, skin), text(title_a, (t_str("TEAM A"),)), text(title_b, (t_str("RESERVES"),)),
                     show(title_a), show(title_b)]))
    cards = []
    for row in range(1, 9):
        local = (row - 1) % 4 + 1
        oi = label("MP party slot %d" % row, 672, 44 + (row - 1) % 4 * 35 + (168 if row > 4 else 0), 108, 35)
        labels.append(oi)
        cards.append(oi)
        owner = (t_func(F_TOSTRING), t_long(local - 1), t_op("mod"), t_gv(G["players"]), t_op("+"), t_long(1), t_close())
        # Ultra's character-name paragraphs end with twelve metadata characters;
        # use the same name extraction as its original character preview.
        name = (t_func(19), t_objexp(3, 81, oi), t_comma(), t_func(22), t_objexp(3, 81, oi),
                t_close(), t_op("-"), t_long(12), t_close())
        extras.append(add([coop(), cond(ids, 2, -49, available, [p_cmp("=", t_long(row))])], [
            act(3, 84, oi, [p_expr(t_altval(2, available, 0))]),
            text(oi, (t_str("P"), t_op("+"), *owner, t_op("+"), t_str("  Slot %d\n" % local), t_op("+"), *name)),
            color(oi, 0xffffff), show(oi)]))
        extras.append(add([coop(), c_gv(ids, slot, "=", t_long(row))], [color(oi, 0x5ad4ff)]))
        extras.append(add([coop(), cond(ids, 2, -49, available, [p_cmp("=", t_long(row))])], [
            act(otype, 91, online, [p_expr(t_long(row)), p_expr(t_altval(2, available, 0)),
                p_expr(t_gv(G["players"])), p_expr(t_gv(G["keyboard_p1"])), p_expr(t_long(oi)), p_expr(t_gv(slot))])]))
        extras.append(add([cond(ids, otype, -114, online, flags=0),
                           c_compare(ids, native(29), "=", (t_long(0),)),
                           c_compare(ids, native(27), "=", (t_long(row),)),
                           cond(ids, 2, -49, available, [p_cmp("=", t_long(row))]),
                           cond(ids, 2, -27, icon, [p_altval(1), p_cmp("=", *native(28))]),
                           cond(ids, 2, -25, icon, [p_expr(t_long(0))])], [
            act(2, 31, available, [p_altval(0), p_expr(*native(28))]), a_set_gv(slot, t_long(row))]))
    portraits = []
    for row in range(1, 9):
        portrait = clone_active(m, f, icon, "MP party portrait %d" % row, 634,
                                44 + (row - 1) % 4 * 35 + (168 if row > 4 else 0))
        portraits.append(portrait)
        extras.append(add([coop(), cond(ids, 2, -49, available, [p_cmp("=", t_long(row))])], [
            act(2, 40, portrait, [p_expr(t_altval(2, available, 0), t_op("-"), t_long(1))]),
            act(2, 85, portrait, [p_expr(t_double(.42)), p_expr(t_long(1))]),
            act(2, 27, portrait)]))
        extras.append(add([coop(), cond(ids, 2, -49, available, [p_cmp("=", t_long(row))]),
                           cond(ids, 2, -27, available, [p_altval(0), p_cmp("<=", t_long(0))])],
                          [act(2, 26, portrait)]))
    borders = []
    for row in range(1, 9):
        y = 42 + (row - 1) % 4 * 35 + (168 if row > 4 else 0)
        for edge, x, top, width, height in (("top", 630, y, 152, 1), ("bottom", 630, y + 33, 152, 1),
                                          ("left", 630, y, 1, 34), ("right", 781, y, 1, 34)):
            border = clone_active(m, f, m.oi("bfx overlay"), "MP party slot %d %s edge" % (row, edge), x, top)
            borders.append(border)
            extras.append(add([coop()], [
                act(2, 40, border, [p_expr(t_long(0))]),
                act(2, 85, border, [p_expr(t_double(1)), p_expr(t_long(0))]),
                act(2, 86, border, [p_expr(t_double(width), t_op("/"), t_objexp(2, 40, border)), p_expr(t_long(0))]),
                act(2, 87, border, [p_expr(t_double(height), t_op("/"), t_objexp(2, 41, border)), p_expr(t_long(0))]),
                act(2, 2, border, [p_expr(t_long(x), t_op("+"), t_objexp(2, 11, border), t_op("-"), t_objexp(2, 7, border))]),
                act(2, 3, border, [p_expr(t_long(top), t_op("+"), t_objexp(2, 1, border), t_op("-"), t_objexp(2, 9, border))]),
                act(2, 65, border, [p_expr(t_long(155))]), act(2, 27, border)]))
            extras.append(add([coop(), c_gv(ids, slot, "=", t_long(row))], [act(2, 65, border, [p_expr(t_long(0))])]))
    focus_outline = m.oi("spr select", f)
    extras.append(add([coop()], [
        act(2, 2, focus_outline, [p_expr(*native(30), t_op("-"), t_long(24))]),
        act(2, 3, focus_outline, [p_expr(*native(31), t_op("+"), t_long(22))]),
        act(2, 40, focus_outline, [p_expr(t_long(0))]), act(2, 27, focus_outline)]))
    extras += [
        add([coop(), c_gv(ids, slot, "<=", t_long(8))], [text(title, (
            t_str("P"), t_op("+"), t_func(F_TOSTRING), t_gv(G["turn_owner"]), t_op("+"), t_long(1), t_close(),
            t_op("+"), t_str(": EDIT YOUR SELECTED SLOT"))), show(title),
            text(prompt, (t_str("Click your P# slot, then a portrait. D-pad + A also works.\nB / R: your next slot. Q / E or LB / RB: category.\nP1: Done / Start to play. Duplicate picks allowed."),)), show(prompt)]),
        add([coop()], [text(cursor, (t_str("v"),)), color(cursor, 0x5ad4ff),
            act(3, 2, cursor, [p_expr(*native(30))]), act(3, 3, cursor, [p_expr(*native(31))]), show(cursor),
            text(pages, (t_str("Roster page "), t_op("+"), t_func(F_TOSTRING), *native(32), t_close(), t_op("+"), t_str(" / "),
                t_op("+"), t_func(F_TOSTRING), *native(33), t_close())), show(pages),
            act(2, 2, previous, [p_expr(t_long(548))]), act(2, 3, previous, [p_expr(t_long(363))]),
            act(2, 88, previous, [p_expr(t_long(90)), p_expr(t_long(1))]), act(2, 27, previous),
            act(2, 2, following, [p_expr(t_long(590))]), act(2, 3, following, [p_expr(t_long(363))]),
            act(2, 88, following, [p_expr(t_long(90)), p_expr(t_long(1))]), act(2, 27, following)]),
    ]
    # Native callbacks never write a guest's profile. These execute only on the
    # authority and feed the same slot objects used by Ultra's existing save loop.
    callback = lambda kind: [cond(ids, otype, -114, online, flags=0), c_compare(ids, native(29), "=", (t_long(kind),))]
    preview_name = (t_func(19), t_objexp(3, 81, preview), t_comma(), t_func(22), t_objexp(3, 81, preview),
                    t_close(), t_op("-"), t_long(12), t_close())
    for unlocked in (False, True):
        extras.append(add([coop(), cond(ids, 2, -27, icon, [p_altval(1), p_cmp("=", *native(34))]),
                           cond(ids, 2, -25 if unlocked else -24, icon, [p_expr(t_long(0))])], [
            act(3, 84, preview, [p_expr(*native(34))]),
            text(preview, (*preview_name, t_op("+"), t_str("   Lv. " if unlocked else "   LOCKED"),
                 *((t_op("+"), t_func(F_TOSTRING), t_altval(2, icon, 2), t_close()) if unlocked else ()))),
            color(preview, 0xffffff if unlocked else 0xa0a0a0), show(preview)]))
    extras += [
        add(callback(1), [act(2, 31, m.oi("spr select", f), [p_altval(1), p_expr(t_long(8))]),
                          a_set_gv(accepted, t_long(1))]),
        add(callback(4), [a_set_gv(slot, *native(27))]),
        add(callback(6), [clone(a) for a in back_event.actions]),
        add(callback(3), [act(2, 31, available, [p_altval(0), p_expr(t_long(0))]), a_set_gv(slot, t_long(1))]),
        *[add(callback(5) + [c_compare(ids, native(27), "=", (t_long(row),)),
                            cond(ids, 2, -49, available, [p_cmp("=", t_long(row))])],
              [act(2, 31, available, [p_altval(0), p_expr(t_long(0))])]) for row in range(1, 9)],
        add([coop(), c_compare(ids, native(35), "=", (t_long(0),))], [act(2, 65, done, [p_expr(t_long(140))])]),
        add([coop(), c_compare(ids, native(35), "=", (t_long(1),))], [act(2, 65, done, [p_expr(t_long(0))])]),
        add([coop()], [act(2, 26, m.oi(name, f)) for name in
            ["plr character", "spr move", "spr available", "spr legacy border"] if any(o.name == name for o in m.objs)] +
            [act(3, 26, m.oi(name, f)) for name in ["txt name", "txt level", "txt next"]] +
            [act(7, 26, m.oi(name, f)) for name in ["cnt level", "cnt next"]]),
        add([solo()], [act(3, 26, oi) for oi in labels] + [act(2, 26, oi) for oi in borders + portraits] +
            [act(otype, 91, online, [p_expr(t_long(0)), p_expr(t_long(0)), p_expr(t_long(1)), p_expr(t_long(0)), p_expr(t_long(0)), p_expr(t_long(0))])]),
        add([cond(ids, -1, -1)], [a_set_gv(accepted, t_long(0))]),
    ]
    b.extend(extras)
    m.sync_groups(f)
    names = []
    props = m.objs[57].props
    offset = struct.unpack_from("<H", props, 36)[0]
    for index in range(struct.unpack_from("<I", props, offset + 12)[0]):
        paragraph = offset + struct.unpack_from("<I", props, offset + 16 + index * 4)[0]
        value = props[paragraph + 8:].decode("utf-16-le").split("\0", 1)[0]
        names.append(value[:-12].strip())
    # Existing colour/costume forms are optional cosmetics. The selected base
    # character still supplies every battle stat and move; unlock checks apply.
    families = {
        "Freddy": ["Shamrock Freddy", "Freddy Frostbear", "Black Ice Freddy", "Mystic Freddy",
                   "Rainbow Freddy", "Emerald Freddy", "Firework Freddy", "Joyful Freddy"],
        "Bonnie": ["Easter Bonnie", "Purple Bonnie", "Black Hearted Bonnie"],
        "Chica": ["Liberty Chica"], "Foxy": ["Radioactive Foxy"],
        "Toy Freddy": ["Golden Toy Freddy", "Aeronaut Toy Freddy", "Woodland Toy Freddy"],
        "Toy Bonnie": ["Sunken Toy Bonnie"], "Toy Chica": ["Catrina Toy Chica"],
        "Funtime Freddy": ["Grey Funtime Freddy", "Black Funtime Freddy"],
    }
    named = {name: index + 1 for index, name in enumerate(names)}
    skins = {str(named[base]): [named[base]] + [named[name] for name in variants if name in named]
             for base, variants in families.items() if base in named}
    return dict(icon=icon, done=done, reset=reset, category=category, previous=previous, following=following,
                cards=cards[0], labels=labels, portraits=portraits, borders=borders, focus=focus_outline,
                title=title, title_a=title_a, title_b=title_b, prompt=prompt, preview=preview,
                cursor=cursor, pages=pages, names=names, skin=skin, skins=skins, back=back)
