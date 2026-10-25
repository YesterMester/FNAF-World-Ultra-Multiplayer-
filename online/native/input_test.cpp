#include "input.hpp"
#include <cassert>
#include <iostream>
int main() {
    auto movement = [](int value) { return (value > 7000 || value < -7000) ? value * 100 / 32768 : 0; };
    for (int raw = -32768; raw <= 32767; ++raw) {
        const auto normalized = fwum::normalize_axis(int16_t(raw));
        assert(movement(normalized) == movement(raw));
        assert(fwum::normalize_axis(normalized) == normalized);
        if (raw >= -7000 && raw <= 7000) assert(normalized == 0);
    }
    std::cout << "All 65536 stick values preserve effective movement without idle noise\n";
}
