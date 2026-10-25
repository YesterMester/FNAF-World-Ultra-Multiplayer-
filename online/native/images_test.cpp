#include "images.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <iostream>

int main() {
    std::array<uint16_t, 6> host{5, 1, 4, 0, 3, 2}, guest{0, 1, 2, 3, 4, 5};
    std::array<uint16_t, 6> host_reverse{}, guest_reverse{};
    for (size_t i = 0; i < host.size(); ++i) host_reverse[host[i]] = uint16_t(i);
    const fwum::ImageMap h{host.data(), host_reverse.data(), host.size(), host.size()};
    unsigned layouts = 0;
    do {
        for (size_t i = 0; i < guest.size(); ++i) guest_reverse[guest[i]] = uint16_t(i);
        const fwum::ImageMap g{guest.data(), guest_reverse.data(), guest.size(), guest.size()};
        for (size_t i = 0; i < host.size(); ++i) {
            const int disk = h.to_disk(int(i)), local = g.to_memory(disk);
            assert(guest[local] == host[i]);
            assert(g.to_disk(local) == disk && h.to_memory(disk) == int(i));
        }
        ++layouts;
    } while (std::next_permutation(guest.begin(), guest.end()));
    assert(layouts == 720);
    auto rejects = [](auto operation) {
        bool rejected = false;
        try { operation(); } catch (const std::runtime_error&) { rejected = true; }
        assert(rejected);
    };
    rejects([&] { h.to_disk(-1); }); rejects([&] { h.to_disk(6); });
    rejects([&] { h.to_memory(-1); }); rejects([&] { h.to_memory(6); });
    host_reverse[0] = UINT16_MAX;
    rejects([&] { h.to_memory(0); });
    host_reverse[0] = 6;
    rejects([&] { h.to_memory(0); });
    host[0] = 6;
    rejects([&] { h.to_disk(0); });
    std::cout << "Stable image identities survive all 720 client bank layouts; unloaded and invalid images are rejected\n";
}
