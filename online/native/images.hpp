#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>

namespace fwum {
// Fusion compacts and reloads each client's image bank independently. Only the
// original file handle identifies the same bitmap on every computer.
struct ImageMap {
    const uint16_t* memory_to_disk;
    const uint16_t* disk_to_memory;
    size_t memory_count, disk_count;
    int to_disk(int image) const {
        if (image < 0 || size_t(image) >= memory_count || memory_to_disk[image] >= disk_count)
            throw std::runtime_error("The game image is unavailable.");
        return memory_to_disk[image];
    }
    int to_memory(int image) const {
        if (image < 0 || size_t(image) >= disk_count || disk_to_memory[image] == UINT16_MAX ||
            disk_to_memory[image] >= memory_count)
            throw std::runtime_error("A required game image has not loaded.");
        return disk_to_memory[image];
    }
};
}
