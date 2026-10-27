"""Helpers for building compiled Fusion events (conditions, actions, expressions).

Encodings were taken from the compiled data of the games being patched; every
helper produces exactly the byte layout the Fusion 2.5+ runtime reads.
"""
import copy
import struct

from .fusion import Act, Cond, EventGroup, Param

# ---------------------------------------------------------------------------
# Expression tokens

OPS = {"+": 2, "-": 4, "*": 6, "/": 8, "mod": 10, "^": 12, "and": 14, "or": 16, "xor": 18}

# Special (system) functions: token num, closed by CLOSE
F_RANDOM = 1
F_TOSTRING = 4
F_ABS = 29
F_TOINT = 28
F_MIN = 40
F_MAX = 41
F_ROUND = 48
F_LOOPINDEX = 46
F_RANDOMRANGE = 65

END = b"\0\0\0\0"


def t_long(v):
    return struct.pack("<hhHi", -1, 0, 10, int(v))


def t_double(v):
    return struct.pack("<hhHdf", -1, 23, 18, float(v), float(v))


def t_str(s):
    data = s.encode("utf-16-le") + b"\0\0"
    return struct.pack("<hhH", -1, 3, 6 + len(data)) + data


def t_gv(index):
    """GlobalValue[index] (0-based)."""
    return struct.pack("<hhHih", -1, 24, 12, 0, index)


def t_op(op):
    return struct.pack("<hhH", 0, OPS[op], 6)


def t_open():
    return struct.pack("<hhH", -1, -1, 6)


def t_close():
    return struct.pack("<hhH", -1, -2, 6)


def t_comma():
    return struct.pack("<hhH", -1, -3, 6)


def t_func(num):
    return struct.pack("<hhH", -1, num, 6)


def t_objexp(otype, num, oi, extra=b""):
    """Object expression (e.g. num 11 X, 1 Y, 15 count); `extra` holds trailing data."""
    return struct.pack("<hhHHh", otype, num, 10 + len(extra), oi, 0) + extra


def t_altval(otype, oi, index):
    return struct.pack("<hhHHhh", otype, 16, 12, oi, 0, index)


def t_objcount(otype, oi):
    return t_objexp(otype, 15, oi)


def t_ext(otype, idx, oi):
    """Extension expression number `idx` (0-based) of object `oi`."""
    return t_objexp(otype, 80 + idx, oi)


def expr(*tokens, cmp=0):
    """Build an expression/comparison parameter body."""
    return struct.pack("<h", cmp) + b"".join(tokens) + END


CMP = {"=": 0, "<>": 1, "<=": 2, "<": 3, ">=": 4, ">": 5}

# ---------------------------------------------------------------------------
# Parameters


def p_expr(*tokens):
    return Param(22, expr(*tokens))


def p_cmp(op, *tokens):
    return Param(23, expr(*tokens, cmp=CMP[op]))


def p_altval(index):
    return Param(50, struct.pack("<hi", index, 0))


def p_global(index):
    return Param(49, struct.pack("<hi", index, 0))


def p_object(otype, oi):
    return Param(1, struct.pack("<hHhh", 0, oi, otype, 0))


def p_loopname(name):
    return Param(45, expr(t_str(name)))


def p_short(code, value):
    return Param(code, struct.pack("<h", value))


# ---------------------------------------------------------------------------
# Conditions / actions


class Ids:
    """Allocates fresh condition identifiers for one frame."""

    def __init__(self, frame):
        used = [c.identifier for g in frame.events.groups for c in g.conditions]
        self.next = max([i for i in used if i < 0] or [-32769]) + 1

    def take(self):
        v = self.next
        self.next += 1
        return v


def cond(ids, otype, num, oi=0, params=(), flags=32, other=0, def_type=0, ident=True):
    c = Cond()
    c.object_type = otype
    c.num = num
    c.object_info = oi
    c.object_info_list = 0
    c.flags = flags
    c.other_flags = other
    c.def_type = def_type
    c.identifier = ids.take() if ident else 0
    c.params = list(params)
    return c


def act(otype, num, oi=0, params=(), flags=0, other=0, def_type=0):
    a = Act()
    a.object_type = otype
    a.num = num
    a.object_info = oi
    a.object_info_list = 0
    a.flags = flags
    a.other_flags = other
    a.def_type = def_type
    a.params = list(params)
    return a


def group(conds, acts, flags=0, line=0, restrict_cpt=0):
    g = EventGroup()
    g.flags = flags
    g.line = line
    g.is_restricted = 0
    g.restrict_cpt = restrict_cpt
    g.conditions = list(conds)
    g.actions = list(acts)
    return g


def clone(x):
    return copy.deepcopy(x)


# Common system conditions/actions
def c_always(ids):
    return cond(ids, -1, -1)


def c_notalways(ids):
    return cond(ids, -1, -7)


def c_compare(ids, left_tokens, op, right_tokens):
    """Special: compare two general values."""
    return cond(ids, -1, -3, params=[Param(22, expr(*left_tokens)), p_cmp(op, *right_tokens)])


def _is_const(tokens):
    return len(tokens) == 1 and tokens[0][:4] == struct.pack("<hh", -1, 0)


def c_gv(ids, index, op, *tokens):
    """Compare a global value. The runtime's integer variants (-28..-33) only
    read a constant, so anything else uses the generic comparison (-8)."""
    if _is_const(tokens):
        num = {"=": -28, "<>": -29, "<=": -30, "<": -31, ">=": -32, ">": -33}[op]
    else:
        num = -8
    return cond(ids, -1, num, params=[p_global(index), p_cmp(op, *tokens)])


def _gv_action(const_num, generic_num, index, tokens):
    return act(-1, const_num if _is_const(tokens) else generic_num,
               params=[p_global(index), p_expr(*tokens)])


def a_set_gv(index, *tokens):
    # 27 = set (integer constant only), 3 = set (any expression)
    return _gv_action(27, 3, index, tokens)


def a_add_gv(index, *tokens):
    return _gv_action(31, 5, index, tokens)


def a_sub_gv(index, *tokens):
    return _gv_action(35, 4, index, tokens)
