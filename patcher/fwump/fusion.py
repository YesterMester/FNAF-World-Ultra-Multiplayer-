"""Object, frame and event structures for Fusion 2.5+ compiled data,
with byte-exact re-serialisation so modified data can be written back."""
import struct
import zlib

from .ccn import Reader, read_chunks, CHUNK_NAMES


CRYPT = {"game": None}   # set to a ccn.Game to allow writing encrypted chunks


def pack_chunk(cid, flag, data, game=None):
    """Serialise one chunk (flags 0 raw, 1 zlib, 2 encrypted, 3 zlib+encrypted)."""
    game = game or CRYPT["game"]
    if flag == 0:
        body = data
    elif flag == 1:
        comp = zlib.compress(data, 6)
        body = struct.pack("<ii", len(data), len(comp)) + comp
    elif flag == 2:
        body = game.decrypter.transform(data)
    elif flag == 3:
        comp = zlib.compress(data, 6)
        inner = bytearray(game.decrypter.transform(struct.pack("<I", len(comp)) + comp))
        if (cid & 1) == 1 and game.build > 284:
            inner[0] ^= ((cid & 0xFF) ^ (cid >> 8)) & 0xFF
        body = struct.pack("<I", len(data)) + bytes(inner)
    else:
        raise ValueError("cannot write chunk flag %d" % flag)
    return struct.pack("<hhi", cid if cid < 0x8000 else cid - 0x10000, flag, len(body)) + body


# --------------------------------------------------------------------------
# Objects (2.5+ split chunks)

class ObjectDef:
    def __init__(self, index):
        self.index = index
        self.header = b""       # 16 bytes from ObjectHeaders
        self.name = ""
        self.shader = b""       # raw entry from ObjectShaders (incl. size)
        self.props = b""        # decompressed ObjectProperties entry

    @property
    def handle(self):
        return struct.unpack_from("<h", self.header, 0)[0]

    @property
    def type(self):
        return struct.unpack_from("<h", self.header, 2)[0]

    @property
    def flags(self):
        return struct.unpack_from("<h", self.header, 4)[0]

    def __repr__(self):
        return "<Obj %d %r type=%d>" % (self.handle, self.name, self.type)


def parse_objects_old(game):
    """Pre-2.5+ layout: one FrameItems chunk holding per-object sub-chunks."""
    c = game.chunk(0x2229) or game.chunk(0x223F)
    data = c.decode(game)
    r = Reader(data)
    n = r.i32()
    objs = []
    pos = r.pos
    for i in range(n):
        subs, pos = read_chunks(data, pos)
        o = ObjectDef(i)
        o.shader = b""
        for sc in subs:
            if sc.id == 0x4444:
                o.header = sc.decode(game)
            elif sc.id == 0x4445:
                rr = Reader(sc.decode(game))
                o.name = rr.wstr() if game.unicode else rr.astr()
            elif sc.id == 0x4446:
                o.props = sc.decode(game)
            elif sc.id == 0x4448:
                o.shader = sc.decode(game)
        objs.append(o)
    return objs


def parse_objects(game):
    if game.chunk(0x2253) is None:
        return parse_objects_old(game)
    hdr = game.chunk(0x2253).decode(game)
    names = game.chunk(0x2254).decode(game)
    shaders = game.chunk(0x2255).decode(game)
    props = game.chunk(0x2256).decode(game)
    offsets = game.chunk(0x2257).decode(game)
    n = len(hdr) // 16
    objs = [ObjectDef(i) for i in range(n)]
    for i, o in enumerate(objs):
        o.header = hdr[i * 16:(i + 1) * 16]
    r = Reader(names)
    for o in objs:
        o.name = r.wstr() if game.unicode else r.astr()
    assert r.pos == len(names), (r.pos, len(names))
    r = Reader(shaders)
    for o in objs:
        start = r.pos
        size = r.i32()
        r.pos += size
        o.shader = shaders[start:r.pos]
    assert r.pos == len(shaders)
    offs = struct.unpack("<%dI" % n, offsets)
    for i, o in enumerate(objs):
        p = offs[i]
        dsize, csize = struct.unpack_from("<ii", props, p)
        raw = props[p + 8:p + 8 + csize]
        o.props = zlib.decompress(raw)
        assert len(o.props) == dsize
        o._props_raw = props[p:p + 8 + csize]
    return objs


def build_object_chunks(game, objs, recompress=None):
    """Return dict chunk_id -> data for the five object chunks."""
    hdr = b"".join(o.header for o in objs)
    names = b"".join(((o.name.encode("utf-16-le") + b"\0\0") if game.unicode
                      else (o.name.encode("latin-1") + b"\0")) for o in objs)
    shaders = b"".join(o.shader for o in objs)
    parts = []
    offs = []
    pos = 0
    for o in objs:
        raw = getattr(o, "_props_raw", None)
        if raw is None or (recompress and o in recompress):
            comp = zlib.compress(o.props, 6)
            raw = struct.pack("<ii", len(o.props), len(comp)) + comp
        offs.append(pos)
        parts.append(raw)
        pos += len(raw)
    props = b"".join(parts)
    offsets = struct.pack("<%dI" % len(objs), *offs)
    return {0x2253: hdr, 0x2254: names, 0x2255: shaders, 0x2256: props, 0x2257: offsets}


# --------------------------------------------------------------------------
# Events

EXPR_PARAM_CODES = {15, 22, 23, 27, 28, 45, 46, 52, 53, 54, 59, 62}


class Param:
    __slots__ = ("code", "data")

    def __init__(self, code, data):
        self.code = code
        self.data = data   # bytes after code

    def serialize(self):
        return struct.pack("<hh", len(self.data) + 4, self.code) + self.data


class Cond:
    __slots__ = ("object_type", "num", "object_info", "object_info_list", "flags",
                 "other_flags", "def_type", "identifier", "params")

    def serialize(self):
        body = struct.pack("<hhHhbbBBh", self.object_type, self.num, self.object_info,
                           self.object_info_list, self.flags, self.other_flags,
                           len(self.params), self.def_type, self.identifier)
        body += b"".join(p.serialize() for p in self.params)
        return struct.pack("<H", len(body) + 2) + body


class Act:
    __slots__ = ("object_type", "num", "object_info", "object_info_list", "flags",
                 "other_flags", "def_type", "params")

    def serialize(self):
        body = struct.pack("<hhHhbbBB", self.object_type, self.num, self.object_info,
                           self.object_info_list, self.flags, self.other_flags,
                           len(self.params), self.def_type)
        body += b"".join(p.serialize() for p in self.params)
        return struct.pack("<H", len(body) + 2) + body


class EventGroup:
    __slots__ = ("flags", "line", "is_restricted", "restrict_cpt", "conditions", "actions")

    def serialize(self):
        body = struct.pack("<BBHhii", len(self.conditions), len(self.actions), self.flags,
                           self.line, self.is_restricted, self.restrict_cpt)
        body += b"".join(c.serialize() for c in self.conditions)
        body += b"".join(a.serialize() for a in self.actions)
        return struct.pack("<h", -(len(body) + 2)) + body


def _read_params(r, count):
    ps = []
    for _ in range(count):
        start = r.pos
        size = r.i16()
        code = r.i16()
        ps.append(Param(code, bytes(r.data[r.pos:start + size])))
        r.pos = start + size
    return ps


def read_event_group(r):
    start = r.pos
    size = r.i16()
    g = EventGroup()
    nc = r.u8()
    na = r.u8()
    g.flags = r.u16()
    g.line = r.i16()
    g.is_restricted = r.i32()
    g.restrict_cpt = r.i32()
    g.conditions = []
    g.actions = []
    for _ in range(nc):
        cs = r.pos
        csize = r.u16()
        c = Cond()
        c.object_type = r.i16()
        c.num = r.i16()
        c.object_info = r.u16()
        c.object_info_list = r.i16()
        c.flags = r.i8()
        c.other_flags = r.i8()
        np_ = r.u8()
        c.def_type = r.u8()
        c.identifier = r.i16()
        c.params = _read_params(r, np_)
        assert r.pos == cs + csize, ("cond size", r.pos, cs + csize)
        g.conditions.append(c)
    for _ in range(na):
        as_ = r.pos
        asize = r.u16()
        a = Act()
        a.object_type = r.i16()
        a.num = r.i16()
        a.object_info = r.u16()
        a.object_info_list = r.i16()
        a.flags = r.i8()
        a.other_flags = r.i8()
        np_ = r.u8()
        a.def_type = r.u8()
        a.params = _read_params(r, np_)
        assert r.pos == as_ + asize, ("act size", r.pos, as_ + asize)
        g.actions.append(a)
    assert r.pos == start - size, ("group size", r.pos, start - size)
    return g


class Events:
    def __init__(self, data):
        r = Reader(data)
        self.sections = []   # ordered list of (tag, payload) for exact rebuild
        self.groups = []
        self.qualifiers = []
        while r.pos < len(data):
            tag = r.bytes(4)
            if tag == b"ER>>":
                self.max_objects = r.i16()
                self.max_object_info = r.i16()
                self.num_players = r.i16()
                self.num_conditions = [r.i16() for _ in range(17)]
                qn = r.i16()
                self.qualifiers = [(r.u16(), r.i16()) for _ in range(qn)]
                self.sections.append((tag, None))
            elif tag == b"ERes":
                self.eres = r.i32()
                self.sections.append((tag, None))
            elif tag == b"ERev":
                size = r.i32()
                end = r.pos + size
                block = []
                while r.pos < end:
                    block.append(read_event_group(r))
                assert r.pos == end
                self.groups.extend(block)
                self.sections.append((tag, block))
            elif tag == b"ERop":
                self.options = r.i32()
                self.sections.append((tag, None))
            elif tag == b"<<ER":
                self.sections.append((tag, None))
                break
            else:
                raise ValueError("unknown event tag %r at %d" % (tag, r.pos - 4))
        self.tail = bytes(data[r.pos:])

    @staticmethod
    def fix_group_pointers(block):
        """Group pointer parameters (code 39, used by activate/deactivate group and
        "group activated") hold the distance from the parameter to the NewGroup
        event of their group in the same block; recompute them after edits."""
        starts = {}
        params = []
        pos = 0
        for g in block:
            p = pos + 16
            for c in g.conditions:
                if c.object_type == -1 and c.num == -10 and c.params and c.params[0].code == 38:
                    gid = struct.unpack_from("<HH", c.params[0].data, 0)[1]
                    starts.setdefault(gid, pos)
                q = p + 16
                for prm in c.params:
                    if prm.code == 39:
                        params.append((prm, q))
                    q += 4 + len(prm.data)
                p += len(c.serialize())
            for a in g.actions:
                q = p + 14
                for prm in a.params:
                    if prm.code == 39:
                        params.append((prm, q))
                    q += 4 + len(prm.data)
                p += len(a.serialize())
            pos = p
        for prm, q in params:
            ptr, gid = struct.unpack_from("<ih", prm.data, 0)
            if gid in starts:
                prm.data = struct.pack("<ih", starts[gid] - q, gid) + prm.data[6:]

    def serialize(self):
        for tag, blk in self.sections:
            if tag == b"ERev":
                self.fix_group_pointers(blk)
        out = bytearray()
        for tag, _ in self.sections:
            out += tag
            if tag == b"ER>>":
                out += struct.pack("<hhh", self.max_objects, self.max_object_info, self.num_players)
                out += struct.pack("<17h", *self.num_conditions)
                out += struct.pack("<h", len(self.qualifiers))
                for q in self.qualifiers:
                    out += struct.pack("<Hh", *q)
            elif tag == b"ERes":
                total = sum(sum(len(g.serialize()) for g in blk)
                            for t, blk in self.sections if t == b"ERev")
                out += struct.pack("<i", total)
            elif tag == b"ERev":
                body = b"".join(g.serialize() for g in _)
                out += struct.pack("<i", len(body)) + body
            elif tag == b"ERop":
                out += struct.pack("<i", self.options)
        out += self.tail
        return bytes(out)


# --------------------------------------------------------------------------
# Frames

class Instance:
    __slots__ = ("handle", "object_info", "x", "y", "parent_type", "parent_handle",
                 "layer", "instance")

    def serialize(self):
        return struct.pack("<HHiihhhh", self.handle, self.object_info, self.x, self.y,
                           self.parent_type, self.parent_handle, self.layer, self.instance)


class Frame:
    def __init__(self, game, chunk):
        self.game = game
        self.chunk = chunk
        data = chunk.decode(game)
        self.subchunks, end = read_chunks(data, 0)
        self.name = None
        self.events = None
        self.instances = None
        for c in self.subchunks:
            if c.id == 0x3335:
                r = Reader(c.decode(game))
                self.name = r.wstr() if game.unicode else r.astr()
            elif c.id == 0x3334:
                r = Reader(c.decode(game))
                self.width = r.i32()
                self.height = r.i32()
                self.background = r.bytes(4)
                self.flags = r.u32()
            elif c.id == 0x3338:
                r = Reader(c.decode(game))
                n = r.i32()
                self.instances = []
                for _ in range(n):
                    it = Instance()
                    it.handle = r.u16()
                    it.object_info = r.u16()
                    it.x = r.i32()
                    it.y = r.i32()
                    it.parent_type = r.i16()
                    it.parent_handle = r.i16()
                    it.layer = r.i16()
                    it.instance = r.i16()
                    self.instances.append(it)
                self._inst_tail = bytes(r.data[r.pos:])
            elif c.id == 0x333D:
                self.events = Events(c.decode(game))
            elif c.id == 0x3341:
                r = Reader(c.decode(game))
                n = r.u32()
                self.layers = []
                for _ in range(n):
                    flags = r.u32()
                    xc = r.f32()
                    yc = r.f32()
                    nb = r.i32()
                    bi = r.i32()
                    nm = r.wstr() if game.unicode else r.astr()
                    self.layers.append((flags, xc, yc, nb, bi, nm))

    def sub(self, cid):
        for c in self.subchunks:
            if c.id == cid:
                return c
        return None

    def instances_bytes(self):
        return (struct.pack("<i", len(self.instances)) +
                b"".join(i.serialize() for i in self.instances) + self._inst_tail)

    def rebuild(self, replace):
        """Return new frame chunk payload; `replace` maps sub-chunk id -> new data."""
        out = bytearray()
        for c in self.subchunks:
            if c.id in replace:
                out += pack_chunk(c.id, c.flag, replace[c.id], self.game)
            else:
                out += struct.pack("<hhi", c.id if c.id < 0x8000 else c.id - 0x10000,
                                   c.flag, len(c.raw)) + bytes(c.raw)
        return bytes(out)


def parse_frames(game):
    return [Frame(game, c) for c in game.chunks if c.id == 0x3333]


# --------------------------------------------------------------------------
# Writing a whole game data file

class NewChunk:
    """A chunk to be written with fresh content."""
    __slots__ = ("id", "flag", "data")

    def __init__(self, cid, flag, data):
        self.id = cid
        self.flag = flag
        self.data = data


def serialize_chunks(chunks):
    out = []
    for c in chunks:
        if isinstance(c, NewChunk):
            out.append(pack_chunk(c.id, c.flag, c.data))
        else:
            cid = c.id if c.id < 0x8000 else c.id - 0x10000
            out.append(struct.pack("<hhi", cid, c.flag, len(c.raw)) + bytes(c.raw))
    return b"".join(out)


def write_game(game, out_path, chunks):
    """Write pack data + game header + `chunks` (+ original trailer) to out_path.

    The runtime refuses to start unless the Protection chunk (0x2242) holds the
    checksum of every byte from the TargetFilename chunk (0x222F) up to the
    Protection chunk itself, so that value is recomputed here."""
    from .checksum import make_pame_checksum
    d = game.data
    head = bytes(d[:game.game_start + 16])  # pack data (or exe stub) + PAMU header
    parts = []
    region_start = None
    prot_index = None
    pos = 0
    for c in chunks:
        if c.id == 0x222F and region_start is None:
            region_start = pos
        if c.id == 0x2242:
            prot_index = len(parts)
            parts.append(None)
            pos += 12
            continue
        blob = serialize_chunks([c])
        parts.append(blob)
        pos += len(blob)
    if prot_index is not None:
        before = b"".join(parts[:prot_index])
        value = make_pame_checksum(before[region_start:])
        parts[prot_index] = pack_chunk(0x2242, 2, struct.pack("<I", value), game)
    with open(out_path, "wb") as f:
        f.write(head)
        for blob in parts:
            f.write(blob)
        f.write(game.trailer)
