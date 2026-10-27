"""Use the original menu actions with per-client D-pad focus and fixed targets."""

from .evb import (
    Ids,
    act,
    c_compare,
    c_gv,
    group,
    p_cmp,
    p_expr,
    t_close,
    t_ext,
    t_long,
    t_objexp,
)
from .party import clone_text


MENU_FRAMES = {
    0,
    1,
    2,
    3,
    4,
    9,
    10,
    11,
    12,
    13,
    15,
    16,
    17,
    18,
    19,
    21,
    22,
    25,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    35,
    36,
    37,
    38,
}


def add_controls(m, otype, online):
    views = {}
    for frame_index in sorted(MENU_FRAMES):
        f = m.frames[frame_index]
        targets = set()
        for g in f.events.groups:
            for c in g.conditions:
                mouse = c.object_type == -6 and (
                    c.num == -7 or frame_index == 33 and c.num == -4
                )
                touch = c.object_type >= 32 and c.num == -87
                oi = m._objparam(c) if mouse or touch else None
                if oi is None or oi >= len(m.objs) or m.objs[oi].type not in (2, 3, 7):
                    continue
                if (
                    m.objs[oi].name.lower().startswith("obj ")
                    or m.objs[oi].name.lower() == "box nose"
                ):
                    continue
                if frame_index == 4 and m.objs[oi].name not in {
                    "hud options",
                    "hud chips",
                    "hud bytes",
                    "hud button",
                    "hud party",
                    "spr map button",
                }:
                    continue
                if frame_index == 25 and oi not in (1168, 1171):
                    continue
                targets.add(oi)
                c.object_type, c.object_info, c.object_info_list = (
                    m.objs[oi].type,
                    oi,
                    0,
                )
                c.num, c.flags, c.def_type = -26, 32, 0
                c.params = [p_cmp("=", t_ext(otype, 43, online), t_long(oi), t_close())]
        night_back = -1
        if frame_index == 33:
            night_back = clone_text(m, f, "MP night back", 625, 446, 170, 24, 70)
            targets.add(night_back)
            ids = Ids(f)
            m.blocks(f)[-1].extend(
                [
                    group(
                        [
                            c_compare(
                                ids,
                                (
                                    t_ext(otype, 43, online),
                                    t_long(night_back),
                                    t_close(),
                                ),
                                ">",
                                (t_long(0),),
                            )
                        ],
                        [act(-3, 2, params=[p_expr(t_long(5))])],
                        line=m.next_line(),
                    ),
                    group(
                        [
                            c_gv(ids, m.G["players"], ">", t_long(1)),
                            c_compare(
                                ids, (t_objexp(7, 80, 1289),), ">=", (t_long(6),)
                            ),
                        ],
                        [act(-3, 2, params=[p_expr(t_long(5))])],
                        line=m.next_line(),
                    ),
                ]
            )
        if not targets:
            continue
        markers = [
            clone_text(m, f, "MP menu focus P%d" % player, -400, -400, 28, 24, 70)
            for player in range(1, 5)
        ]
        back = next(
            (
                oi
                for oi in sorted(targets)
                if m.objs[oi]
                .name.lower()
                .startswith(
                    ("btt back", "btt return", "back button", "btt done", "btt exit")
                )
            ),
            -1,
        )
        if night_back >= 0:
            back = night_back
        preferred = next(
            (
                oi
                for oi in sorted(targets)
                if m.objs[oi].name.lower()
                in ("btt start", "btt continue", "btt slot", "btt chips")
            ),
            -1,
        )
        if frame_index == 4:
            preferred = next(
                (oi for oi in targets if m.objs[oi].name == "hud party"), -1
            )
        if frame_index == 25:
            preferred = 1171
        priorities = (
            "btt continue",
            "btt slot",
            "btt start",
            "spr slot",
            "spr shop slot",
            "btt done",
            "btt chips",
        )
        preferences = [
            oi
            for name in priorities
            for oi in sorted(targets)
            if m.objs[oi].name.lower() == name
        ]
        views[frame_index] = dict(
            controls=sorted(targets),
            markers=markers,
            back_control=back,
            preferred=preferred,
            preferences=preferences,
            auto_focus=frame_index not in (4, 18, 19, 21),
            world=frame_index == 4,
            host_only=frame_index in (0, 1, 2, 9, 10, 31, 32),
            keyboard_global=m.G["keyboard_p1"],
            players_global=m.G["players"],
        )
        if frame_index == 31:
            views[frame_index].update(
                slider_knob=m.oi("btt slider", f),
                slider_track=m.oi("box slider", f),
                control_hint=clone_text(
                    m, f, "MP options controls", 230, 450, 510, 22, 70
                ),
            )
        if frame_index == 33:
            views[frame_index].update(
                control_hint=clone_text(
                    m, f, "MP night controls", 20, 448, 580, 22, 70
                ),
                hint_text="Co-op office: share cameras and tasks.  D-pad + A.  B: leave",
                night_back=night_back,
            )
        m.sync_groups(f)
    m.log("D-pad menu targets added to %d screens" % len(views))
    return views
