#include "input.hpp"
#include <cassert>
#include <iostream>
int main() {
    fwum::ActionLatch latch;
    assert(latch.filter(0x1001) == 1); // Held A cannot cross a scene; movement can.
    assert(latch.filter(0x1001) == 1);
    assert(latch.filter(0) == 0);
    assert(latch.filter(0x1001) == 0x1001);
    latch.arm();
    assert(latch.filter(fwum::mouse_target_button) == 0);
    assert(latch.filter(0) == 0);
    assert(latch.filter(fwum::mouse_target_button) == fwum::mouse_target_button);
    for (uint32_t target : {0u, 1u, 65535u, 65536u, 0x80008000u, 0xffffffffu})
        assert(fwum::mouse_target(fwum::mouse_target_low(target), fwum::mouse_target_high(target)) == target);
    auto movement = [](int value) { return (value > 7000 || value < -7000) ? value * 100 / 32768 : 0; };
    for (int raw = -32768; raw <= 32767; ++raw) {
        const auto normalized = fwum::normalize_axis(int16_t(raw));
        assert(movement(normalized) == movement(raw));
        assert(fwum::normalize_axis(normalized) == normalized);
        if (raw >= -7000 && raw <= 7000) assert(normalized == 0);
    }
    std::cout << "All 65536 stick values preserve effective movement without idle noise\n";
}
