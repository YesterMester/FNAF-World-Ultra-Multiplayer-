#include "snapshot.hpp"
#include <cassert>
#include <limits>
#include <iostream>
int main() {
    fwum::Snapshot s; s.frame = 4; s.sequence = 52; s.camera_x = 700;
    s.layers.push_back({100, 200, 16});
    fwum::Entity freddy; freddy.id = 123; freddy.oi = 317; freddy.x = 800; freddy.y = 250;
    freddy.image = 901; freddy.scale_x = .75f; freddy.value = 9.5; freddy.text = u"P2: Freddy \u2605";
    freddy.z = 42; freddy.sprite_layer = 3;
    freddy.minimum = -10; freddy.maximum = 200; freddy.floating = true; freddy.colour = 0x123456;
    s.entities.push_back(freddy);
    auto data = fwum::encode(s); auto result = fwum::decode(data);
    assert(result.frame == 4 && result.sequence == 52 && result.camera_x == 700);
    assert(result.entities[0].image == 901 && result.entities[0].value == 9.5 && result.entities[0].text == freddy.text);
    assert(result.layers[0].x == 100 && result.layers[0].flags == 16);
    assert(result.entities[0].z == 42 && result.entities[0].sprite_layer == 3);
    assert(result.entities[0].minimum == -10 && result.entities[0].maximum == 200 && result.entities[0].floating);
    assert(result.entities[0].colour == 0x123456);
    for (size_t i = 0; i < data.size(); ++i) {
        bool rejected = false;
        try { fwum::decode(std::vector<uint8_t>(data.begin(), data.begin() + i)); }
        catch (const std::runtime_error&) { rejected = true; }
        assert(rejected);
    }
    s.entities[0].scale_x = std::numeric_limits<float>::quiet_NaN();
    bool rejected = false;
    try { fwum::decode(fwum::encode(s)); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    std::cout << "snapshot round trip, UTF-16 text, all truncated packets, and invalid numbers passed\n";
}
