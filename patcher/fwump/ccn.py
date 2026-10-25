"""Reader for compiled Clickteam Fusion 2.5 game data (PAME/PAMU).

Format knowledge follows CTFAK 2.0 (AGPL) and Anaconda's mmfparser.
"""
import struct
import zlib

CHUNK_NAMES = {
    0x1122: "Preview", 0x2222: "MiniHeader", 0x2223: "Header", 0x2224: "Name",
    0x2225: "Author", 0x2226: "Menu", 0x2227: "ExtPath", 0x2228: "Extensions",
    0x2229: "FrameItems", 0x222A: "GlobalEvents", 0x222B: "FrameHandles",
    0x222C: "ExtData", 0x222D: "AdditionalExtension", 0x222E: "EditorFilename",
    0x222F: "TargetFilename", 0x2230: "AppDoc", 0x2231: "OtherExtensions",
    0x2232: "GlobalValues", 0x2233: "GlobalStrings", 0x2234: "ExtensionList",
    0x2235: "Icon", 0x2236: "DemoVersion", 0x2237: "SerialNumber",
    0x2238: "BinaryFiles", 0x2239: "MenuImages", 0x223A: "AboutText",
    0x223B: "Copyright", 0x223C: "GlobalValueNames", 0x223D: "GlobalStringNames",
    0x223E: "MovementExtensions", 0x223F: "FrameItems2", 0x2240: "ExeOnly",
    0x2242: "Protection", 0x2243: "Shaders", 0x2245: "ExtendedHeader",
    0x2246: "Spacer", 0x2247: "FrameOffset", 0x2248: "AdMobId",
    0x224B: "AndroidMenu", 0x2253: "ObjectHeaders", 0x2254: "ObjectNames",
    0x2255: "ObjectShaders", 0x2256: "ObjectProperties", 0x2258: "FontInfo",
    0x2259: "Fonts", 0x225A: "Shaders2",
    0x3333: "Frame", 0x3334: "FrameHeader", 0x3335: "FrameName",
    0x3336: "FramePassword", 0x3337: "FramePalette", 0x3338: "FrameItemInstances",
    0x3339: "FrameFadeInFrame", 0x333A: "FrameFadeOutFrame", 0x333B: "FrameFadeIn",
    0x333C: "FrameFadeOut", 0x333D: "FrameEvents", 0x333E: "FramePlayHeader",
    0x333F: "AdditionalFrameItem", 0x3340: "AdditionalFrameItemInstance",
    0x3341: "FrameLayers", 0x3342: "FrameVirtualRect", 0x3343: "DemoFilePath",
    0x3344: "RandomSeed", 0x3345: "FrameLayerEffects", 0x3346: "BluRayOptions",
    0x3347: "MvtTimerBase", 0x3348: "MosaicImageTable", 0x3349: "FrameEffects",
    0x334A: "FrameIphoneOptions",
    0x4444: "ObjectInfoHeader", 0x4445: "ObjectInfoName", 0x4446: "ObjectCommon",
    0x4447: "ObjectUnknown", 0x4448: "ObjectEffects", 0x4500: "ObjectShapes",
    0x5555: "ImageOffsets", 0x5556: "FontOffsets", 0x5557: "SoundOffsets",
    0x5558: "MusicOffsets", 0x6665: "BankOffsets", 0x6666: "Images",
    0x6667: "FontBank", 0x6668: "Sounds", 0x6669: "Music",
    0x7EEE: "Fusion3Seed", 0x7F7F: "Last",
}

OBJECT_TYPES = {
    -7: "Player", -6: "Keyboard", -5: "Create", -4: "Timer", -3: "Game",
    -2: "Speaker", -1: "System", 0: "QuickBackdrop", 1: "Backdrop", 2: "Active",
    3: "Text", 4: "Question", 5: "Score", 6: "Lives", 7: "Counter", 8: "RTF",
    9: "SubApplication",
}


class Reader:
    __slots__ = ("data", "pos")

    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def size(self):
        return len(self.data)

    def remaining(self):
        return len(self.data) - self.pos

    def _unpack(self, fmt, n):
        v = struct.unpack_from(fmt, self.data, self.pos)[0]
        self.pos += n
        return v

    def i8(self): return self._unpack("<b", 1)
    def u8(self): return self._unpack("<B", 1)
    def i16(self): return self._unpack("<h", 2)
    def u16(self): return self._unpack("<H", 2)
    def i32(self): return self._unpack("<i", 4)
    def u32(self): return self._unpack("<I", 4)
    def f32(self): return self._unpack("<f", 4)
    def f64(self): return self._unpack("<d", 8)

    def bytes(self, n):
        b = bytes(self.data[self.pos:self.pos + n])
        self.pos += n
        return b

    def peek_u16(self):
        return struct.unpack_from("<H", self.data, self.pos)[0]

    def wstr(self, n=-1):
        if n >= 0:
            s = bytes(self.data[self.pos:self.pos + n * 2]).decode("utf-16-le", "replace")
            self.pos += n * 2
            return s
        end = self.pos
        d = self.data
        while end + 1 < len(d) and (d[end] or d[end + 1]):
            end += 2
        s = bytes(d[self.pos:end]).decode("utf-16-le", "replace")
        self.pos = min(end + 2, len(d))
        return s

    def astr(self, n=-1):
        if n >= 0:
            s = bytes(self.data[self.pos:self.pos + n]).decode("latin-1")
            self.pos += n
            return s
        end = self.pos
        d = self.data
        while end < len(d) and d[end]:
            end += 1
        s = bytes(d[self.pos:end]).decode("latin-1")
        self.pos = min(end + 1, len(d))
        return s


# --------------------------------------------------------------------------
# Decryption (chunk flags 2 and 3)

MAGIC_CHAR = 54


def _key_string(s):
    out = bytearray()
    for ch in s or "":
        c = ord(ch)
        if c & 0xFF:
            out.append(c & 0xFF)
        if (c >> 8) & 0xFF:
            out.append((c >> 8) & 0xFF)
    return out


def _make_key_combined(data):
    data_len = len(data)
    key = bytearray(256)
    key[:data_len] = data
    last = MAGIC_CHAR
    v34 = MAGIC_CHAR
    for i in range(data_len + 1):
        v34 = ((v34 << 7) + (v34 >> 1)) & 0xFF
        key[i] ^= v34
        last = (last + key[i] * ((v34 & 1) + 2)) & 0xFF
    key[data_len + 1] = last
    return key


def _rotate(v):
    return ((v << 7) | (v >> 1)) & 0xFF


class Decrypter:
    def __init__(self, s1, s2, s3):
        key = _make_key_combined(_key_string(s1) + _key_string(s2) + _key_string(s3))
        table = list(range(256))
        accum = MAGIC_CHAR
        h = MAGIC_CHAR
        never_reset = True
        i2 = 0
        k = 0
        for i in range(256):
            h = _rotate(h)
            if never_reset:
                accum = (accum + (2 if (h & 1) == 0 else 3)) & 0xFF
                accum = (accum * key[k]) & 0xFF
            if h == key[k]:
                h = _rotate(MAGIC_CHAR)
                k = 0
                never_reset = False
            i2 = (i2 + ((h ^ key[k]) + table[i])) & 0xFF
            table[i2], table[i] = table[i], table[i2]
            k = (k + 1) & 0xFF
        self.table = table

    def transform(self, data):
        t = list(self.table)
        out = bytearray(data)
        i = 0
        i2 = 0
        for j in range(len(out)):
            i = (i + 1) & 0xFF
            i2 = (i2 + t[i]) & 0xFF
            t[i], t[i2] = t[i2], t[i]
            out[j] ^= t[(t[i] + t[i2]) & 0xFF]
        return bytes(out)


# --------------------------------------------------------------------------
# Chunks

class Chunk:
    __slots__ = ("id", "flag", "raw", "offset", "_data")

    def __init__(self, cid, flag, raw, offset):
        self.id = cid
        self.flag = flag
        self.raw = raw
        self.offset = offset
        self._data = None

    @property
    def name(self):
        return CHUNK_NAMES.get(self.id, "0x%04X" % self.id)

    def decode(self, ctx):
        if self._data is not None:
            return self._data
        raw = self.raw
        f = self.flag
        if f == 0:
            d = bytes(raw)
        elif f == 1:
            dsize, csize = struct.unpack_from("<ii", raw, 0)
            d = zlib.decompress(bytes(raw[8:8 + csize]))
        elif f == 2:
            d = ctx.decrypter.transform(raw)
        elif f == 3:
            dsize = struct.unpack_from("<I", raw, 0)[0]
            body = bytearray(raw[4:])
            if (self.id & 1) == 1 and ctx.build > 284:
                body[0] ^= ((self.id & 0xFF) ^ (self.id >> 8)) & 0xFF
            body = ctx.decrypter.transform(body)
            csize = struct.unpack_from("<I", body, 0)[0]
            d = zlib.decompress(bytes(body[4:4 + csize]))
        else:
            raise ValueError("unknown chunk flag %d" % f)
        self._data = d
        return d


def read_chunks(data, pos=0, end=None, stop_at_last=True):
    end = len(data) if end is None else end
    chunks = []
    while pos + 8 <= end:
        cid, flag, size = struct.unpack_from("<hhi", data, pos)
        cid &= 0xFFFF
        off = pos
        pos += 8
        raw = data[pos:pos + size]
        pos += size
        chunks.append(Chunk(cid, flag, raw, off))
        if stop_at_last and cid == 0x7F7F:
            break
    return chunks, pos


# --------------------------------------------------------------------------
# Pack data ("wwww") that precedes the game data

class PackFile:
    def __init__(self, name, bingo, data, compressed):
        self.name = name
        self.bingo = bingo
        self.data = data
        self.compressed = compressed


def read_packdata(data, start):
    r = Reader(data, start)
    header = r.bytes(8)
    assert header[:4] == b"wwww", header
    header_size = r.u32()
    data_size = r.u32()
    r.pos = start + data_size - 32
    magic = r.bytes(4)
    r.pos = start + 16
    fmt = r.u32()
    r.i32()
    r.i32()
    count = r.u32()
    files = []
    for _ in range(count):
        n = r.u16()
        name = r.wstr(n)
        bingo = r.i32()
        size = r.i32()
        raw = r.bytes(size)
        files.append(PackFile(name, bingo, raw, raw[:2] == b"\x78\xda"))
    assert r.pos == start + data_size - 32, (r.pos, start + data_size - 32)
    return files, r.pos, magic


def find_game_start(data):
    """Return (pack_start, game_start) for an exe or a separate .dat file."""
    if data[:4] == b"wwww":
        pack_start = 0
    elif data[:2] == b"MZ":
        pe = struct.unpack_from("<I", data, 60)[0]
        nsec = struct.unpack_from("<H", data, pe + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe + 20)[0]
        sec = pe + 24 + opt_size
        end = 0
        for i in range(nsec):
            s = sec + i * 40
            name = bytes(data[s:s + 8]).rstrip(b"\0")
            rsize, rptr = struct.unpack_from("<II", data, s + 16)
            if name == b".extra":
                end = rptr
                break
            end = max(end, rptr + rsize)
        pack_start = end
    else:
        raise ValueError("unknown container")
    return pack_start


class Game:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = memoryview(f.read())
        d = self.data
        self.pack_start = find_game_start(d)
        self.packfiles, self.game_start, _ = read_packdata(d, self.pack_start)
        r = Reader(d, self.game_start)
        self.magic = r.bytes(4)
        self.unicode = self.magic == b"PAMU"
        self.runtime_version = r.u16()
        self.runtime_subversion = r.u16()
        self.product_version = r.i32()
        self.build = r.i32()
        self.chunks, self.game_end = read_chunks(d, r.pos)
        self.trailer = bytes(d[self.game_end:])
        self.decrypter = None
        self._strings()

    def str_chunk(self, c):
        data = c.decode(self)
        r = Reader(data)
        return r.wstr() if self.unicode else r.astr()

    def _strings(self):
        self.name = self.copyright = self.editor_filename = None
        for c in self.chunks:
            if c.id == 0x2224:
                self.name = self.str_chunk(c)
            elif c.id == 0x223B:
                self.copyright = self.str_chunk(c)
            elif c.id == 0x222E:
                self.editor_filename = self.str_chunk(c)
                if self.build > 284:
                    self.decrypter = Decrypter(self.name, self.copyright, self.editor_filename)
                else:
                    self.decrypter = Decrypter(self.editor_filename, self.name, self.copyright)

    def chunks_by_id(self, cid):
        return [c for c in self.chunks if c.id == cid]

    def chunk(self, cid):
        for c in self.chunks:
            if c.id == cid:
                return c
        return None
