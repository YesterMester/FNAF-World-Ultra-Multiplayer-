#pragma once
#include <algorithm>
#include <array>
#include <string>
#include <vector>

namespace fwum {
// Freeze encounter ownership by member identity, so removing or inserting a
// seat cannot give the next character's turn to a different person.
class BattleOwners {
    std::array<std::string, 4> members{};
public:
    void clear() { members.fill({}); }
    void begin(const std::vector<std::string>& current) {
        clear();
        if (current.empty()) return;
        for (size_t slot = 0; slot < members.size(); ++slot) members[slot] = current[slot % current.size()];
    }
    int owner(int slot, const std::vector<std::string>& current) const {
        if (slot < 1 || slot > 4 || current.empty()) return 0;
        const auto found = std::find(current.begin(), current.end(), members[slot - 1]);
        return found == current.end() ? 0 : int(found - current.begin());
    }
};

class BattleHealth {
    struct Slot { double a = 0, b = 0, maximum_a = 0, maximum_b = 0; };
    std::array<Slot, 4> slots{};
    unsigned seen = 0;
public:
    void begin_tick() { seen = 0; }
    void set(int slot, double a, double b, double maximum_a, double maximum_b) {
        if (slot < 1 || slot > 4) return;
        slots[slot - 1] = {a, b, maximum_a, maximum_b}; seen |= 1u << (slot - 1);
    }
    bool ready() const {
        return seen == 15 && std::all_of(slots.begin(), slots.end(), [](const auto& s) {
            return s.maximum_a > 0 && s.maximum_b > 0;
        });
    }
    int living() const {
        if (!ready()) return -1;
        int result = 0;
        for (const auto& s : slots) result += int(s.a > 0) + int(s.b > 0);
        return result;
    }
    int replacement(unsigned teams) const {
        if (!ready()) return 0;
        for (size_t i = 0; i < slots.size(); ++i) {
            const auto& s = slots[i];
            const bool reserve = teams & (1u << i);
            if ((reserve ? s.b : s.a) <= 0 && (reserve ? s.a : s.b) > 0) return int(i) + 1;
        }
        return 0;
    }
    std::array<std::array<double, 4>, 4> values() const {
        std::array<std::array<double, 4>, 4> result{};
        for (size_t i = 0; i < slots.size(); ++i)
            result[i] = {slots[i].a, slots[i].b, slots[i].maximum_a, slots[i].maximum_b};
        return result;
    }
};
}
