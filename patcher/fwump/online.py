"""Inject the native lobby/input/replication extension into the merged game."""
import hashlib
import os
import struct
import sys
from pathlib import Path

from .evb import Ids, act, a_set_gv, c_compare, clone, cond, expr, group, p_expr, t_ext, t_close, t_long, t_objexp, t_gv
from .fusion import EXPR_PARAM_CODES, ObjectDef, Param
from .merge import MergeError

PUBLIC_RELAY = "wss://fwum-relay.famous-cry.workers.dev/lobbies"

def find_extension():
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(__file__).resolve().parents[2]]
    for root in roots:
        for path in (root / "FWUMOnline.mfx", root / "build/online/FWUMOnline.mfx"):
            if path.is_file():
                return str(path)
    return None


def add_online(m, module):
    if not os.path.isfile(module):
        raise MergeError("native online extension not found: %s" % module)
    count, slots = struct.unpack_from("<HH", m.ext_chunk)
    name = "FWUMOnline.mfx".encode("utf-16-le") + b"\0\0"
    entry = struct.pack("<HHIII", 16 + len(name) + 2, slots, 0, 0, 0) + name + b"\0\0"
    m.ext_chunk = struct.pack("<HH", count + 1, slots + 1) + m.ext_chunk[4:] + entry
    o = ObjectDef(len(m.objs))
    otype = 32 + slots
    o.header = struct.pack("<hh", o.index, otype) + m.objs[m.xoi].header[4:]
    o.name = "MP Online"
    o.shader = b"\0\0\0\0"
    props = bytearray(90)
    struct.pack_into("<I", props, 0, len(props))
    struct.pack_into("<H", props, 12, 70)  # extension EDITDATA
    struct.pack_into("<I", props, 16, 0x6000)  # never kill / never sleep
    struct.pack_into("<8h", props, 20, *([-1] * 8))
    struct.pack_into("<I", props, 46, 0x4E4D5746)
    struct.pack_into("<IIIII", props, 70, 20, 20, 0, 0, 0)
    o.props = bytes(props)
    m.objs.append(o)

    def infinite_loop(a):
        if a.object_type != -2 or a.num != 12 or len(a.params) != 3:
            return False
        p = a.params[2].data
        return len(p) >= 12 and p[2:6] == struct.pack("<hh", -1, 0) and struct.unpack_from("<i", p, 8)[0] == 0

    # Music may continue across areas. Every frame needs the same callbacks so
    # late joins can restore the currently playing loop using local sound assets.
    music = {}
    shader_names, shader_params, shader_objects = {}, {}, {}
    def shader_targets(a):
        if a.object_info < 32768:
            return [a.object_info]
        return [ob.index for ob in m.objs if ob.type == a.object_type and len(ob.props) >= 36 and
                (a.object_info & 32767) in struct.unpack_from("<8h", ob.props, 20)]
    for f in m.frames:
        for g in f.events.groups:
            for a in g.actions:
                if infinite_loop(a):
                    music.setdefault(a.serialize(), clone(a))
                if a.object_type in (2, 3, 7) and a.num in (63, 64):
                    table = shader_names if a.num == 63 else shader_params
                    key = a.params[0].data
                    if a.num == 64 and (a.params[0].code != 45 or key[2:6] != struct.pack("<hh", -1, 3)):
                        raise MergeError("dynamic shader parameter names are unsupported")
                    table.setdefault(key, len(table))
                    for oi in shader_targets(a):
                        shader_objects.setdefault(oi, {63: set(), 64: set()})[a.num].add(key)
    music_ids = {key: 32768 + i for i, key in enumerate(music)}
    if len(music_ids) > 32768:
        raise MergeError("too many music callbacks")
    if len(shader_names) > 32768 or len(shader_params) > 256:
        raise MergeError("too many shader names or parameters")

    def audio_hook(audio_id, a):
        channel = p_expr(t_long(0))
        value = p_expr(t_long(0))
        sample = -1
        if a.num in (0, 4, 6, 7, 8, 11, 12) and a.params and a.params[0].code == 6:
            sample = struct.unpack_from("<H", a.params[0].data)[0]
        if a.num in (11, 12, 13, 14, 15, 16, 17, 18, 32):
            p = a.params[1 if a.num in (11, 12) else 0]
            channel = Param(22, p.data)
        if a.num in (17, 18, 32):
            value = Param(22, a.params[1].data)
        return act(otype, 84, o.index, [p_expr(t_long(audio_id)), p_expr(t_long(a.num)),
                                       channel, p_expr(t_long(sample)), value])

    def rewrite_parameter(parameter):
        if parameter.code not in EXPR_PARAM_CODES:
            return
        data = bytearray(parameter.data)
        offset = 2
        while offset + 4 <= len(data):
            typ, num = struct.unpack_from("<hh", data, offset)
            if typ == 0 and num == 0:
                break
            if offset + 6 > len(data):
                raise MergeError("incomplete expression while adding online controls")
            size = struct.unpack_from("<H", data, offset + 4)[0]
            if size < 6 or offset + size > len(data):
                raise MergeError("invalid expression while adding online controls")
            if typ == m.xtype and size >= 10 and struct.unpack_from("<H", data, offset + 6)[0] == m.xoi:
                struct.pack_into("<h", data, offset, otype)
                struct.pack_into("<H", data, offset + 6, o.index)
            offset += size
        parameter.data = bytes(data)

    move_buttons = {ob.index for ob in m.objs if ob.name == "mov button"}
    for frame_index, f in enumerate(m.frames):
        ids = Ids(f)
        original_groups = {id(g) for g in f.events.groups}
        used_lines = {g.line for g in f.events.groups}
        audio_events = []
        # Native clients render the host's state. Ultra's own events only run on
        # the authority, so remote players never write the host's save locally.
        for g in list(f.events.groups):
            for item in g.conditions + g.actions:
                if item.object_type == m.xtype and item.object_info == m.xoi:
                    item.object_type, item.object_info = otype, o.index
                for parameter in item.params:
                    rewrite_parameter(parameter)
            if any(c.object_type == -1 and c.num in (-10, -11) for c in g.conditions):
                continue  # structural group markers must retain their layout
            gated = []
            for c in g.conditions:
                if c.object_type == -1 and c.num in (-24, -25):
                    gated.append(cond(ids, otype, -81 - 16, o.index))
                gated.append(c)
            gated.append(cond(ids, otype, -81 - 16, o.index))
            if len(gated) > 255:
                raise MergeError("too many conditions in an event after adding online mode")
            g.conditions = gated
            if any(c.object_type == -6 and c.num == -1 and any(p.code == 14 and
                   struct.unpack_from("<H", p.data)[0] == 120 for p in c.params) for c in g.conditions):
                # Native sessions already assign one player per computer.
                g.conditions.append(cond(ids, otype, -81 - 22, o.index, other=1))
            if any(c.object_type >= 32 and c.num == -87 and m._objparam(c) in move_buttons for c in g.conditions):
                # The host's mouse follows the same owner as controller input.
                # Offline mouse assistance retains its original behavior.
                g.conditions.append(cond(ids, otype, -81 - 32, o.index, [p_expr(t_gv(m.G["turn_mask"]))]))
            actions = []
            for a in g.actions:
                actions.append(a)
                if a.object_type == -2:
                    audio_id = music_ids.get(a.serialize())
                    if audio_id is None:
                        audio_id = len(audio_events)
                        if audio_id >= 32768:
                            raise MergeError("too many transient sound callbacks")
                        audio_events.append(clone(a))
                    actions.append(audio_hook(audio_id, a))
                if a.object_type in (2, 3, 7) and a.num in (63, 64):
                    table = shader_names if a.num == 63 else shader_params
                    for oi in shader_targets(a):
                        params = [p_expr(t_long(oi)), p_expr(t_long(table[a.params[0].data]))]
                        if a.num == 64:
                            params.append(Param(22, a.params[1].data))
                        actions.append(act(otype, 86 if a.num == 63 else 87, o.index, params))
            if len(actions) > 255:
                raise MergeError("too many actions in an event after adding online mode")
            g.actions = actions
        m.ensure_instance(f, o.index)
        # Load the original gamepad in every frame for unchanged offline controls.
        m.ensure_instance(f, m.xoi)
        blocks = m.blocks(f)
        expression = lambda idx: (t_ext(otype, idx, o.index), t_close())
        condition = lambda idx, *params: cond(ids, otype, -81 - idx, o.index, params,
                                              flags=0 if idx in (18, 19, 20, 23, 24, 26, 27, 28, 29, 30, 31) else 32)
        def callback(idx, value):
            # Fusion can treat the first triggered condition as already true.
            # Filter the callback explicitly, then select its precise instance.
            expression_index = 7 if idx == 18 else 9 if idx == 23 else 8
            conditions = [condition(idx), c_compare(ids, expression(expression_index), "=", (t_long(value),))]
            if idx in (19, 20, 24, 26, 28, 29, 30, 31):
                conditions.append(condition(25))
            return conditions
        blocks[0][0:0] = [
            group([cond(ids, -1, -1)], [act(otype, 80, o.index, [p_expr(t_long(frame_index))])]),
            group([condition(17)], [act(-3, 2, params=[p_expr(*expression(2))])]),
            group([condition(21)], [act(otype, 83, o.index), act(-3, 5)]),
            group([condition(22)], [a_set_gv(m.G["keyboard_p1"], t_long(0))]),
        ]
        for audio_id, a in enumerate(audio_events):
            blocks[-1].append(group(callback(23, audio_id), [a, audio_hook(-1, a)]))
        for key, a in music.items():
            audio_id = music_ids[key]
            blocks[-1].append(group(callback(23, audio_id), [clone(a), audio_hook(audio_id, a)]))
        for opcode in (13, 14, 15, 17):
            a = act(-2, opcode, params=[p_expr(*expression(10))] +
                    ([p_expr(*expression(11))] if opcode == 17 else []))
            blocks[-1].append(group([condition(27), c_compare(ids, expression(12), "=", (t_long(opcode),))],
                                    [a, audio_hook(-1, a)]))
        # Each frame can instantiate only object types already used by that frame.
        references = {i.object_info: i for i in f.instances if m.objs[i.object_info].type in (2, 3, 7)}
        creates = {}
        for g in f.events.groups:
            for a in g.actions:
                for p in a.params:
                    if p.code == 9 and len(p.data) >= 30:
                        oi = struct.unpack_from("<H", p.data, 24)[0]
                        if oi < len(m.objs) and m.objs[oi].type in (2, 3, 7):
                            creates[oi] = p.data
        for oi in sorted(set(references) | set(creates)):
            typ = m.objs[oi].type
            data = bytearray(creates.get(oi, b"\0" * 30))
            struct.pack_into("<hhhhhhi", data, 0, -1, 8, 0, 0, 0, 0, 0)
            struct.pack_into("<hhh", data, 16, 0, 0, 0)
            if oi not in creates:
                struct.pack_into("<HHI", data, 22, references[oi].handle, oi, 0)
            blocks[-1].append(group(callback(18, oi), [
                act(-5, 0, params=[Param(9, bytes(data))]), act(otype, 82, o.index)]))
            if typ == 3:
                blocks[-1].append(group(callback(19, oi), [
                    act(typ, 88, oi, [Param(45, expr(*expression(5)))])]))
            if typ == 7:
                blocks[-1].append(group(callback(24, oi), [
                    act(typ, 80, oi, [p_expr(*expression(6))])]))
                blocks[-1].append(group(callback(26, oi), [
                    act(otype, 85, o.index, [p_expr(t_objexp(7, 80, oi))])]))
            blocks[-1].append(group(callback(20, oi), [act(typ, 27, oi)]))
            blocks[-1].append(group(callback(30, oi), [act(otype, 88, o.index, [
                p_expr(t_objexp(typ, 27, oi)), p_expr(t_objexp(typ, 28, oi))])]))
            blocks[-1].append(group(callback(31, oi), [
                act(typ, 65, oi, [p_expr(*expression(16))]),
                act(typ, 66, oi, [p_expr(*expression(17))])]))
            blocks[-1].append(group(callback(28, oi) + [
                c_compare(ids, expression(13), "=", (t_long(-1),))],
                [act(typ, 63, oi, [Param(64, b"\0\0")])]))
            for key in sorted(shader_objects.get(oi, {}).get(63, ())):
                blocks[-1].append(group(callback(28, oi) + [
                    c_compare(ids, expression(13), "=", (t_long(shader_names[key]),))],
                    [act(typ, 63, oi, [Param(64, key)])]))
            for key in sorted(shader_objects.get(oi, {}).get(64, ())):
                blocks[-1].append(group(callback(29, oi) + [
                    c_compare(ids, expression(14), "=", (t_long(shader_params[key]),))],
                    [act(typ, 64, oi, [Param(45, key), p_expr(*expression(15))])]))
        blocks[-1].extend([
            group([cond(ids, otype, -81 - 16, o.index, other=1)], [
                act(-3, 8, params=[p_expr(*expression(3))]),
                act(-3, 9, params=[p_expr(*expression(4))])]),
            group([cond(ids, -1, -1)], [act(otype, 81, o.index)]),
        ])
        free_lines = (n for n in range(1, 32768) if n not in used_lines)
        for block in blocks:
            for g in block:
                if id(g) not in original_groups:
                    try:
                        g.line = next(free_lines)
                    except StopIteration:
                        raise MergeError("no free event identifiers for online mode in %r" % f.name)
        m.sync_groups(f)
    m.log("native online lobby and replication hooks added to %d frames" % len(m.frames))


def compatibility_id(m, module):
    """Hash game semantics, independent of the OS's zlib compression output."""
    h = hashlib.sha256(m.ultra.data)
    h.update(m.ext_chunk)
    h.update(m.build_globals())
    for o in m.objs:
        h.update(o.header)
        h.update(o.name.encode("utf-16-le") + b"\0\0")
        h.update(o.props)
    for f in m.frames:
        h.update(f.events.serialize())
        h.update(f.instances_bytes())
    h.update(Path(module).read_bytes())
    h.update(m.mfx_bytes)
    return h.hexdigest()


def default_relay():
    if os.environ.get("FWUM_RELAY_URL"):
        return os.environ["FWUM_RELAY_URL"]
    for root in (Path(getattr(sys, "_MEIPASS", "")), Path(__file__).resolve().parents[2] / "build/online"):
        path = root / "FWUM-server.txt"
        if path.is_file():
            endpoint = path.read_text(encoding="utf-8").strip()
            if endpoint:
                return endpoint
    return PUBLIC_RELAY


def write_settings(out_dir, relay_url=None, build_id=None):
    """Hash the patched data, without changing an existing player name/service."""
    import configparser
    out = Path(out_dir)
    cfg = configparser.ConfigParser(interpolation=None)
    path = out / "FWUM-online.ini"
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("online"):
        cfg.add_section("online")
    if build_id is None:
        raise MergeError("online build compatibility ID was not computed")
    cfg.set("online", "build", build_id)
    if relay_url is not None or not cfg.get("online", "server", fallback="").strip():
        cfg.set("online", "server", relay_url or default_relay())
    if not cfg.has_option("online", "name"):
        cfg.set("online", "name", "Player")
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)
