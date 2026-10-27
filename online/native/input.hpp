#pragma once
#include <algorithm>
#include <cstdint>

namespace fwum {
// XInput reserves this button bit. While it is set, the two axis words carry
// the host's fixed object ID for a mouse selection instead of stick movement.
// The relay already validates and forwards these words without modification.
constexpr uint16_t mouse_target_button = 0x0800;
struct ActionLatch {
    bool waiting = true;
    void arm() { waiting = true; }
    uint16_t filter(uint16_t buttons) {
        constexpr uint16_t actions = 0xfff0;
        if (!waiting) return buttons;
        if (!(buttons & actions)) waiting = false;
        return buttons & ~actions;
    }
};
inline uint32_t mouse_target(int16_t low, int16_t high) {
    return uint32_t(uint16_t(low)) | (uint32_t(uint16_t(high)) << 16);
}
inline int16_t mouse_target_low(uint32_t target) { return int16_t(uint16_t(target)); }
inline int16_t mouse_target_high(uint32_t target) { return int16_t(uint16_t(target >> 16)); }

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
