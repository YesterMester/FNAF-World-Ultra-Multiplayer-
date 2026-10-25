#pragma once
#include <algorithm>
#include <cstdint>

namespace fwum {
// Preserve the movement percentage Fusion actually uses, while ignoring stick
// noise inside its dead zone and changes that produce the same percentage.
inline int16_t normalize_axis(int16_t value) {
    const int magnitude = value < 0 ? -int(value) : int(value);
    if (magnitude <= 7000) return 0;
    const int percent = magnitude * 100 / 32768;
    const int quantized = std::max(7001, (percent * 32768 + 99) / 100);
    return int16_t(value < 0 ? -quantized : quantized);
}
}
