#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace fwum {
constexpr size_t max_packet = 2 * 1024 * 1024;
struct Entity {
    uint32_t id = 0;
    uint16_t oi = 0, layer = 0;
    uint16_t sprite_layer = 0;
    int32_t z = 0;
    uint8_t type = 2, direction = 0;
    int32_t x = 0, y = 0, image = 0, animation = 0;
    float scale_x = 1, scale_y = 1, angle = 0;
    uint32_t effect = 0, effect_param = 0;
    double value = 0;
    double minimum = 0, maximum = 0;
    bool floating = false;
    uint32_t colour = 0xffffff, colour2 = 0xffffff;
    std::u16string text;
};
struct Snapshot {
    uint32_t sequence = 0;
    uint16_t frame = 0, width = 800, height = 450;
    int32_t camera_x = 0, camera_y = 0;
    struct Layer { int32_t x = 0, y = 0; uint32_t flags = 0; };
    uint32_t background = 0;
    std::vector<Layer> layers;
    std::vector<Entity> entities;
};
struct Writer {
    std::vector<uint8_t> data;
    template<class T> void put(T v) {
        static_assert(sizeof(T) <= 8);
        uint64_t bits = 0; std::memcpy(&bits, &v, sizeof v);
        for (size_t i = 0; i < sizeof v; ++i) data.push_back(uint8_t(bits >> (8 * i)));
        if (data.size() > max_packet) throw std::runtime_error("World state is too large.");
    }
};
struct Reader {
    const std::vector<uint8_t>& data; size_t pos = 0;
    template<class T> T get() {
        if (pos + sizeof(T) > data.size()) throw std::runtime_error("Incomplete world state.");
        uint64_t bits = 0;
        for (size_t i = 0; i < sizeof(T); ++i) bits |= uint64_t(data[pos++]) << (8 * i);
        T v; std::memcpy(&v, &bits, sizeof v); return v;
    }
};
inline std::vector<uint8_t> encode(const Snapshot& s) {
    if (s.entities.size() > 4096) throw std::runtime_error("Too many visible objects.");
    Writer w;
    w.put<uint8_t>(0x53); w.put<uint8_t>(2); w.put<uint16_t>(s.frame); w.put<uint32_t>(s.sequence);
    w.put<int32_t>(s.camera_x); w.put<int32_t>(s.camera_y);
    w.put<uint16_t>(s.width); w.put<uint16_t>(s.height); w.put<uint32_t>(s.background);
    if (s.layers.size() > 128) throw std::runtime_error("Too many world layers.");
    w.put<uint16_t>(s.layers.size());
    for (const auto& l : s.layers) { w.put<int32_t>(l.x); w.put<int32_t>(l.y); w.put<uint32_t>(l.flags); }
    w.put<uint16_t>(s.entities.size());
    for (const auto& e : s.entities) {
        w.put<uint32_t>(e.id); w.put<uint16_t>(e.oi); w.put<uint16_t>(e.layer);
        w.put<uint16_t>(e.sprite_layer); w.put<int32_t>(e.z);
        w.put<uint8_t>(e.type); w.put<uint8_t>(e.direction);
        w.put<int32_t>(e.x); w.put<int32_t>(e.y); w.put<int32_t>(e.image); w.put<int32_t>(e.animation);
        w.put<float>(e.scale_x); w.put<float>(e.scale_y); w.put<float>(e.angle);
        w.put<uint32_t>(e.effect); w.put<uint32_t>(e.effect_param); w.put<double>(e.value);
        w.put<double>(e.minimum); w.put<double>(e.maximum); w.put<uint8_t>(e.floating ? 1 : 0);
        w.put<uint32_t>(e.colour); w.put<uint32_t>(e.colour2);
        const auto size = std::min<size_t>(4096, e.text.size());
        w.put<uint16_t>(size);
        for (size_t i = 0; i < size; ++i) w.put<uint16_t>(e.text[i]);
    }
    return std::move(w.data);
}
inline Snapshot decode(const std::vector<uint8_t>& data) {
    if (data.size() > max_packet) throw std::runtime_error("World state is too large.");
    Reader r{data}; Snapshot s;
    if (r.get<uint8_t>() != 0x53 || r.get<uint8_t>() != 2) throw std::runtime_error("Incompatible world state.");
    s.frame = r.get<uint16_t>(); s.sequence = r.get<uint32_t>();
    s.camera_x = r.get<int32_t>(); s.camera_y = r.get<int32_t>();
    s.width = r.get<uint16_t>(); s.height = r.get<uint16_t>();
    s.background = r.get<uint32_t>();
    const auto layers = r.get<uint16_t>();
    if (layers > 128) throw std::runtime_error("Invalid world layers.");
    for (unsigned i = 0; i < layers; ++i) {
        Snapshot::Layer l; l.x = r.get<int32_t>(); l.y = r.get<int32_t>(); l.flags = r.get<uint32_t>();
        if (std::abs(int64_t(l.x)) > 1000000 || std::abs(int64_t(l.y)) > 1000000 || (l.flags & ~0x7ffffu)) {
            throw std::runtime_error("Invalid world layer.");
        }
        s.layers.push_back(l);
    }
    const auto count = r.get<uint16_t>();
    if (s.frame > 255 || count > 4096 || !s.width || !s.height || s.width > 8192 || s.height > 8192 ||
        std::abs(int64_t(s.camera_x)) > 1000000 || std::abs(int64_t(s.camera_y)) > 1000000) {
        throw std::runtime_error("Invalid world state dimensions.");
    }
    for (unsigned i = 0; i < count; ++i) {
        Entity e;
        e.id = r.get<uint32_t>(); e.oi = r.get<uint16_t>(); e.layer = r.get<uint16_t>();
        e.sprite_layer = r.get<uint16_t>(); e.z = r.get<int32_t>();
        e.type = r.get<uint8_t>(); e.direction = r.get<uint8_t>();
        e.x = r.get<int32_t>(); e.y = r.get<int32_t>(); e.image = r.get<int32_t>(); e.animation = r.get<int32_t>();
        e.scale_x = r.get<float>(); e.scale_y = r.get<float>(); e.angle = r.get<float>();
        e.effect = r.get<uint32_t>(); e.effect_param = r.get<uint32_t>(); e.value = r.get<double>();
        e.minimum = r.get<double>(); e.maximum = r.get<double>(); const auto floating = r.get<uint8_t>();
        e.floating = floating != 0; e.colour = r.get<uint32_t>(); e.colour2 = r.get<uint32_t>();
        auto len = r.get<uint16_t>();
        if ((e.type != 2 && e.type != 3 && e.type != 7) || e.direction > 31 || e.layer > 128 || e.sprite_layer > 258 ||
            len > 4096 || e.image < 0 || e.image > 1000000 || (e.effect & ~0x10ffu) || (e.effect & 0xff) > 15 ||
            !std::isfinite(e.scale_x) || !std::isfinite(e.scale_y) || !std::isfinite(e.angle) || !std::isfinite(e.value) ||
            !std::isfinite(e.minimum) || !std::isfinite(e.maximum) || e.minimum > e.maximum || floating > 1 ||
            (e.floating && std::abs(e.value) > std::numeric_limits<float>::max()) ||
            std::abs(e.scale_x) > 100 || std::abs(e.scale_y) > 100 ||
            std::abs(int64_t(e.x)) > 1000000 || std::abs(int64_t(e.y)) > 1000000) {
            throw std::runtime_error("Invalid world object.");
        }
        while (len--) e.text.push_back(char16_t(r.get<uint16_t>()));
        s.entities.push_back(std::move(e));
    }
    if (r.pos != data.size()) throw std::runtime_error("Unexpected world state data.");
    return s;
}
}
