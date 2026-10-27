#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace fwum {
struct FocusTarget { uint32_t id; float x, y; };
inline uint32_t move_focus(const std::vector<FocusTarget>& targets, uint32_t current, int dx, int dy) {
    if (targets.empty()) return 0;
    const auto from = std::find_if(targets.begin(), targets.end(), [current](const auto& t) { return t.id == current; });
    if (from == targets.end()) return targets.front().id;
    uint32_t result = current;
    float best = std::numeric_limits<float>::max();
    for (const auto& target : targets) {
        const float x = target.x - from->x, y = target.y - from->y;
        const float along = x * dx + y * dy, cross = std::abs(x * dy - y * dx);
        if (target.id != current && along > 1 && along + 3 * cross < best) {
            best = along + 3 * cross; result = target.id;
        }
    }
    if (result != current) return result;
    // At an edge, wrap within the nearest row or column.
    for (const auto& target : targets) {
        const float x = target.x - from->x, y = target.y - from->y;
        const float along = x * dx + y * dy, cross = std::abs(x * dy - y * dx);
        if (target.id != current && along < -1 && along + 100 * cross < best) {
            best = along + 100 * cross; result = target.id;
        }
    }
    return result;
}
}
