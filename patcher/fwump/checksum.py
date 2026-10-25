import struct
def make_checksum(data):
    result = 0
    n = len(data)
    reads = n >> 2
    if reads:
        for v in struct.unpack_from("<%dI" % reads, data, 0):
            result = (v + (result >> 31) + 2 * result) & 0xFFFFFFFF
    off = reads * 4
    for i in range(n & 3):
        result = ((result >> 31) + data[off + i] + 2 * result) & 0xFFFFFFFF
    return result

def make_pame_checksum(data):
    c = make_checksum(data)
    return (c & 0xFFFFFF00) | ((c & 0xFF) ^ 13)
